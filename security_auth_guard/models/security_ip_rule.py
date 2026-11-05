# -*- coding: utf-8 -*-
import contextlib
import ipaddress
import logging

import requests

from odoo import SUPERUSER_ID, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# One IPv6 connection normally controls a whole /64 and can move around
# it freely, so a single address is no more meaningful than one port.
IPV6_BLOCK_PREFIX = 64

# Addresses that stand in for many people, so an automatic block would
# cut off everyone behind them. Seeing one as a client address means the
# proxy isn't passing on the real visitor address. Listed explicitly
# because ipaddress's is_private also covers documentation ranges.
LOCAL_PROXY_RANGES = (
    "127.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
    "100.64.0.0/10", "169.254.0.0/16", "::1/128", "fc00::/7", "fe80::/10",
)
# https://www.cloudflare.com/ips-v4 and ips-v6, as of 2026-11-05: the
# starting point, added to daily by _cron_refresh_cloudflare_ranges. Add
# other proxies with the protected_ranges system parameter.
CLOUDFLARE_RANGES = (
    "173.245.48.0/20", "103.21.244.0/22", "103.22.200.0/22", "103.31.4.0/22",
    "141.101.64.0/18", "108.162.192.0/18", "190.93.240.0/20",
    "188.114.96.0/20", "197.234.240.0/22", "198.41.128.0/17",
    "162.158.0.0/15", "104.16.0.0/13", "104.24.0.0/14", "172.64.0.0/13",
    "131.0.72.0/22", "2400:cb00::/32", "2606:4700::/32", "2803:f800::/32",
    "2405:b500::/32", "2405:8100::/32", "2a06:98c0::/29", "2c0f:f248::/32",
)
CLOUDFLARE_API_URL = "https://api.cloudflare.com/client/v4/ips"
# Protecting too much would quietly switch off automatic blocking, so a
# response has to look like Cloudflare's real one. Today that's 15 IPv4 and
# 7 IPv6 ranges, the widest /13 and /29.
CLOUDFLARE_MIN_RANGES = {4: 8, 6: 3}
CLOUDFLARE_WIDEST_PREFIX = {4: 10, 6: 24}


def parse_cloudflare_ranges(payload):
    """The validated ranges from Cloudflare's API response. Raises
    ValueError if anything about it looks wrong.
    """
    if not isinstance(payload, dict) or not payload.get("success"):
        raise ValueError("response did not report success")
    result = payload.get("result") or {}
    ranges = []
    for version, key in ((4, "ipv4_cidrs"), (6, "ipv6_cidrs")):
        entries = result.get(key) or []
        if len(entries) < CLOUDFLARE_MIN_RANGES[version]:
            raise ValueError(f"only {len(entries)} IPv{version} ranges")
        for entry in entries:
            network = ipaddress.ip_network(entry)
            if (network.version != version or not network.is_global
                    or network.prefixlen < CLOUDFLARE_WIDEST_PREFIX[version]):
                raise ValueError(f"implausible range {entry}")
            ranges.append(str(network))
    return ranges


@contextlib.contextmanager
def own_transaction(env):
    """A separate, committed transaction for security records that are
    written just before an error rolls back the request's own one.
    """
    with env.registry.cursor() as cr:
        new_env = api.Environment(cr, SUPERUSER_ID, {})
        new_env.transaction.default_env = new_env
        yield new_env


def parse_address(ip):
    """The address as an ipaddress object, with an IPv4-mapped IPv6
    address unwrapped to the IPv4 address it really is. None if invalid.
    """
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return None
    return getattr(address, "ipv4_mapped", None) or address


def block_target(ip):
    """What counts as one source: the address itself for IPv4, its /64
    for IPv6. Anything unparseable is returned unchanged.
    """
    address = parse_address(ip)
    if address is None:
        return ip
    if address.version == 6:
        return str(ipaddress.ip_network(
            (address, IPV6_BLOCK_PREFIX), strict=False))
    return str(address)


class SecurityIpRule(models.Model):
    """A manual or auto-escalated allow/block list, enforced in
    ir.http._dispatch - the earliest point in Odoo's own request
    handling. An 'allow' rule always wins over a matching 'block' rule,
    so it can be used as a deliberate override (e.g. an office IP that
    would otherwise fall inside a blocked CIDR range).
    """
    _name = "security.ip_rule"
    _description = "Security IP Rule"
    _order = "create_date desc"

    ip_or_cidr = fields.Char(
        required=True, help="A single IP (e.g. 203.0.113.5) or a CIDR "
                             "range (e.g. 203.0.113.0/24).")
    action = fields.Selection(
        [("block", "Block"), ("allow", "Allow")],
        default="block", required=True)
    reason = fields.Char()
    expires_at = fields.Datetime(
        help="Leave blank for a permanent rule.")
    active = fields.Boolean(default=True)

    @api.constrains("ip_or_cidr")
    def _check_ip_or_cidr(self):
        for rule in self:
            try:
                ipaddress.ip_network(rule.ip_or_cidr, strict=False)
            except ValueError as exc:
                raise ValidationError(
                    f'"{rule.ip_or_cidr}" is not a valid IP address or '
                    f'CIDR range.') from exc

    @api.model
    def _is_blocked(self, ip):
        """True if `ip` should be refused. An active, non-expired
        'allow' match always wins over a matching 'block'.
        """
        address = parse_address(ip)
        if address is None:
            return False
        now = fields.Datetime.now()
        rules = self.sudo().search([
            "|", ("expires_at", "=", False), ("expires_at", ">", now)])
        matched_actions = set()
        for rule in rules:
            try:
                network = ipaddress.ip_network(rule.ip_or_cidr, strict=False)
            except ValueError:
                continue
            if address in network:
                matched_actions.add(rule.action)
        if "allow" in matched_actions:
            return False
        return "block" in matched_actions

    @api.model
    def _protected_networks(self):
        """Ranges _block_ip refuses: the built-in lists, the ranges last
        fetched from Cloudflare, and the comma-separated
        security_auth_guard.protected_ranges parameter.
        """
        ICP = self.env["ir.config_parameter"].sudo()
        extra = ICP.get_param("security_auth_guard.protected_ranges", "")
        fetched = ICP.get_param("security_auth_guard.cloudflare_ranges", "")
        networks = []
        for entry in (*LOCAL_PROXY_RANGES, *CLOUDFLARE_RANGES,
                      *fetched.split(","), *extra.split(",")):
            entry = entry.strip()
            if not entry:
                continue
            try:
                networks.append(ipaddress.ip_network(entry, strict=False))
            except ValueError:
                _logger.warning(
                    "Ignoring invalid protected range %r in "
                    "security_auth_guard.protected_ranges.", entry)
        return networks

    @api.model
    def _cron_refresh_cloudflare_ranges(self):
        """Only ever adds to the protected list. A failed fetch keeps what's
        already there, and a range Cloudflare has retired just stays exempt
        from automatic blocks.
        """
        try:
            response = requests.get(CLOUDFLARE_API_URL, timeout=30)
            response.raise_for_status()
            ranges = parse_cloudflare_ranges(response.json())
        except (requests.RequestException, ValueError, TypeError) as exc:
            _logger.warning("Could not refresh Cloudflare ranges: %s", exc)
            return
        self.env["ir.config_parameter"].sudo().set_param(
            "security_auth_guard.cloudflare_ranges", ",".join(ranges))

    @api.model
    def _is_protected(self, ip):
        address = parse_address(ip)
        return address is not None and any(
            address in network for network in self._protected_networks())

    @api.model
    def _block_ip(self, ip, reason):
        """Create a permanent block for `ip` (its /64 for IPv6), or
        extend an existing active one's reason rather than creating a
        duplicate. Returns an empty recordset, blocking nothing, if `ip`
        is protected. Rules created by hand aren't checked, so an admin
        can still make that call deliberately.
        """
        if self._is_protected(ip):
            _logger.warning(
                "Refusing to block protected address %s: %s", ip, reason)
            return self.browse()
        target = block_target(ip)
        existing = self.sudo().search([
            ("ip_or_cidr", "=", target), ("action", "=", "block"),
            ("active", "=", True)], limit=1)
        if existing:
            existing.reason = reason
            return existing
        _logger.warning("Auto-blocking %s: %s", target, reason)
        return self.sudo().create({
            "ip_or_cidr": target, "action": "block", "reason": reason})
