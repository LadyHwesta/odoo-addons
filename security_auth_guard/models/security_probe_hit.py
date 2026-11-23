# -*- coding: utf-8 -*-
import logging
from datetime import timedelta
from urllib.parse import unquote

from odoo import api, fields, models

from .security_ip_rule import block_target

_logger = logging.getLogger(__name__)

DEFAULT_PROBE_THRESHOLD = 3          # probe requests ...
PROBE_WINDOW_MINUTES = 10            # ... within this many minutes
DEFAULT_PROBE_BLOCK_HOURS = 24       # how long the block lasts
DEFAULT_PROBE_PERMANENT_AFTER = 3    # temporary blocks before a permanent one
PERMANENT_WINDOW_DAYS = 30

# Whole path segments that only attackers ask for: secrets and version
# control left in a web root, other platforms' admin pages and scripts.
# wp-content and wp-includes are left out on purpose: a site moved from
# WordPress still has old pages and emails linking images there.
PROBE_SEGMENTS = {
    ".git", ".svn", ".hg", ".aws", ".ssh", ".docker", ".vscode", ".idea",
    ".ds_store", ".htaccess", ".htpasswd", ".npmrc", ".bash_history",
    "wp-admin", "wp-login.php", "xmlrpc.php", "wlwmanifest.xml",
    "phpmyadmin", "pma", "myadmin", "cgi-bin", "phpunit", "actuator",
    "server-status", "boaform", "hnap1",
}
# File types Odoo never serves from a page address.
PROBE_SUFFIXES = (".php", ".asp", ".aspx", ".jsp", ".cgi", ".sql", ".bak")
# Reaching outside the web root.
PROBE_FRAGMENTS = ("../", "..\\", "/etc/passwd", "win.ini", "/proc/self/")


def probe_reason(path, query=""):
    """What makes this address a probe, or None for an ordinary one.

    Only ever asked about addresses Odoo has already answered "not found"
    for, so a real page, redirect or file can never match.
    """
    decoded_path = unquote(unquote(path or "")).lower()
    decoded_query = unquote(unquote(query or "")).lower()
    for fragment in PROBE_FRAGMENTS:
        if fragment in decoded_path or fragment in decoded_query:
            return fragment
    for segment in decoded_path.split("/"):
        if segment in PROBE_SEGMENTS:
            return segment
        if segment.startswith(".env"):
            return ".env"
    if decoded_path.endswith(PROBE_SUFFIXES):
        return "*" + decoded_path[decoded_path.rfind("."):]
    return None


def _int_param(env, key, default):
    try:
        value = int(env["ir.config_parameter"].sudo().get_param(key, default))
    except (TypeError, ValueError):
        return default
    return value or default


class SecurityProbeHit(models.Model):
    """One request for an address only attackers ask for. Kept a day, just
    long enough to count them; the block and its event are the record.
    """
    _name = "security.probe_hit"
    _description = "Security Probe Request"
    _order = "create_date desc"

    ip = fields.Char(required=True)
    source = fields.Char(
        required=True, index=True,
        help="The address, or its /64 for IPv6: what gets counted and blocked.")
    path = fields.Char()
    reason = fields.Char()

    @api.autovacuum
    def _gc_old_hits(self):
        self.sudo().search([
            ("create_date", "<", fields.Datetime.now() - timedelta(days=1)),
        ]).unlink()

    @api.model
    def _record(self, ip, path, reason):
        """Count one probe from `ip`; block it once there are enough.
        Returns the block rule when this request triggered one.
        """
        threshold = _int_param(
            self.env, "security_auth_guard.probe_block_threshold",
            DEFAULT_PROBE_THRESHOLD)
        if threshold < 0:
            return None
        source = block_target(ip)
        self.sudo().create({
            "ip": ip, "source": source, "path": (path or "")[:250],
            "reason": reason})
        since = fields.Datetime.now() - timedelta(minutes=PROBE_WINDOW_MINUTES)
        count = self.sudo().search_count([
            ("source", "=", source), ("create_date", ">=", since)])
        if count < threshold:
            return None
        return self._block(ip, count, path)

    @api.model
    def _block(self, ip, count, path):
        Event = self.env["security.event"].sudo()
        IpRule = self.env["security.ip_rule"].sudo()
        if IpRule._is_blocked(ip):
            # A parallel request got here first; don't count it twice
            # towards a permanent block.
            return None
        hours = max(1, _int_param(
            self.env, "security_auth_guard.probe_block_hours",
            DEFAULT_PROBE_BLOCK_HOURS))
        permanent_after = _int_param(
            self.env, "security_auth_guard.probe_permanent_after",
            DEFAULT_PROBE_PERMANENT_AFTER)
        now = fields.Datetime.now()
        earlier_blocks = Event._count_from_source(
            "probe_blocked", ip, now - timedelta(days=PERMANENT_WINDOW_DAYS))
        permanent = permanent_after > 0 and earlier_blocks + 1 >= permanent_after
        how_long = "permanently" if permanent else f"for {hours}h"
        reason = (f"Probing: {count} requests for attack addresses in "
                  f"{PROBE_WINDOW_MINUTES} min (latest {path})")
        rule = IpRule._block_ip(
            ip, reason, expires_at=None if permanent else now + timedelta(hours=hours))
        if not rule:
            if not Event._count_from_source(
                    "anomaly", ip, now - timedelta(hours=1)):
                Event.create({
                    "event_type": "anomaly", "severity": "critical",
                    "source_ip": ip,
                    "detail": f"{ip} probed for attack addresses ({count} in "
                              f"{PROBE_WINDOW_MINUTES} min, latest {path}) but "
                              f"is a proxy or private address, so it was not "
                              f"blocked. Check that the proxy is passing on "
                              f"real visitor addresses.",
                })
            return None
        # Every probe from here on is refused before it's counted, so this
        # runs once per block.
        Event.create({
            "event_type": "probe_blocked", "severity": "warning",
            "source_ip": ip,
            "detail": f"Blocked {rule.ip_or_cidr} {how_long} after {count} "
                      f"requests for attack addresses in "
                      f"{PROBE_WINDOW_MINUTES} min (latest {path}).",
        })
        return rule
