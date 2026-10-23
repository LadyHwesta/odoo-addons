# -*- coding: utf-8 -*-
import ipaddress
import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


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
        try:
            address = ipaddress.ip_address(ip)
        except ValueError:
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
    def _block_ip(self, ip, reason):
        """Create a permanent block for `ip`, or extend an existing
        active one's reason rather than creating a duplicate.
        """
        existing = self.sudo().search([
            ("ip_or_cidr", "=", ip), ("action", "=", "block"),
            ("active", "=", True)], limit=1)
        if existing:
            existing.reason = reason
            return existing
        _logger.warning("Auto-blocking IP %s: %s", ip, reason)
        return self.sudo().create({
            "ip_or_cidr": ip, "action": "block", "reason": reason})
