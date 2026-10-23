# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class SecurityEvent(models.Model):
    """The one unified security log every piece of this module (and
    anything that extends it, e.g. a financial-anomaly monitor) posts
    to - one place to see everything, not a different screen per source.
    """
    _name = "security.event"
    _description = "Security Event"
    _inherit = ["mail.thread"]
    _order = "create_date desc"

    event_type = fields.Selection(
        [("login_cooldown", "Login Cooldown Triggered"),
         ("ip_blocked", "IP Blocked"),
         ("anomaly", "Anomaly")],
        required=True, tracking=True)
    severity = fields.Selection(
        [("info", "Info"), ("warning", "Warning"), ("critical", "Critical")],
        default="warning", required=True, tracking=True)
    source_ip = fields.Char()
    login = fields.Char(help="The login string involved, if any.")
    partner_id = fields.Many2one("res.partner")
    model_name = fields.Char(
        string="Model", help="Technical name of the affected model, for a "
                              "record-level anomaly.")
    res_id = fields.Integer(string="Record ID")
    detail = fields.Text()
    state = fields.Selection(
        [("new", "New"), ("reviewed", "Reviewed"), ("escalated", "Escalated")],
        default="new", required=True, tracking=True)

    def action_mark_reviewed(self):
        self.write({"state": "reviewed"})

    def action_escalate_to_block(self):
        """Create (or extend) a permanent security.ip_rule block for
        this event's source IP. Manual escalation from the dashboard -
        the automatic version lives on res.users' own cooldown override.
        """
        IpRule = self.env["security.ip_rule"]
        for event in self:
            if not event.source_ip:
                continue
            IpRule._block_ip(
                event.source_ip,
                _("Escalated from security.event #%(id)s", id=event.id))
        self.write({"state": "escalated"})

    @api.model
    def _notify_critical(self, event):
        """Optional, soft integration: send an SMS for a critical event
        if signalwire_sms/signalwire_voip happens to be installed -
        checked at runtime, never a hard dependency, so this module
        installs standalone anywhere.
        """
        if event.severity != "critical":
            return
        Phone = self.env.get("signalwire.phone_number")
        if Phone is None:
            return
        number = self.env["ir.config_parameter"].sudo().get_param(
            "security_auth_guard.alert_phone_number")
        if not number:
            return
        sender = Phone.sudo().search([], limit=1)
        if not sender:
            return
        try:
            sender.send_sms(
                number, _(
                    "Security alert (%(severity)s): %(detail)s",
                    severity=event.severity, detail=event.detail or event.event_type))
        except Exception:
            # Best-effort - a notification failure must never block the
            # security event itself from being recorded.
            pass

    @api.model_create_multi
    def create(self, vals_list):
        events = super().create(vals_list)
        for event in events:
            self._notify_critical(event)
        return events
