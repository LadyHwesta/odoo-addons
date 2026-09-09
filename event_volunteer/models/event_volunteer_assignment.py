# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_ACTIVE_STATES = ("draft", "confirmed")


class EventVolunteerAssignment(models.Model):
    _name = "event.volunteer.assignment"
    _description = "Event Volunteer Assignment"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "event_date_begin desc, id desc"
    _rec_name = "display_name"

    role_id = fields.Many2one(
        "event.volunteer.role", string="Role", required=True,
        ondelete="cascade", index=True, tracking=True)
    event_id = fields.Many2one(
        related="role_id.event_id", store=True, index=True, string="Event")
    event_date_begin = fields.Datetime(
        related="event_id.date_begin", store=True, string="Event Start")
    partner_id = fields.Many2one(
        "res.partner", string="Volunteer", required=True,
        ondelete="cascade", index=True, tracking=True)
    state = fields.Selection(
        selection=[
            ("draft", "Pending"),
            ("confirmed", "Confirmed"),
            ("cancelled", "Cancelled"),
        ],
        default="confirmed", required=True, tracking=True)
    source = fields.Selection(
        selection=[("backoffice", "Back office"), ("portal", "Website")],
        default="backoffice", readonly=True)
    note = fields.Char(string="Note", help="e.g. availability, preferences.")
    reminder_sent = fields.Boolean(default=False, copy=False, readonly=True)

    @api.depends("partner_id", "role_id.name", "event_id.name")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "%s - %s (%s)" % (
                rec.role_id.name or _("Role"),
                rec.partner_id.name or _("Volunteer"),
                rec.event_id.name or "",
            )

    # ------------------------------------------------------------------
    # Guards: one active sign-up per person per role, and don't exceed the
    # role's slot count. Both skippable via context for a bulk fix-up.
    # ------------------------------------------------------------------
    @api.constrains("role_id", "partner_id", "state")
    def _check_assignment(self):
        if self.env.context.get("skip_volunteer_capacity"):
            return
        for rec in self:
            if rec.state not in _ACTIVE_STATES:
                continue
            dup = self.search_count([
                ("id", "!=", rec.id),
                ("role_id", "=", rec.role_id.id),
                ("partner_id", "=", rec.partner_id.id),
                ("state", "in", _ACTIVE_STATES),
            ])
            if dup:
                raise ValidationError(_(
                    "%(name)s is already signed up for %(role)s.",
                    name=rec.partner_id.name, role=rec.role_id.name))
        for role in self.role_id:
            if role.slot_count and role.filled_count > role.slot_count:
                raise ValidationError(_(
                    "The %(role)s role for %(event)s only needs %(n)s "
                    "volunteer(s). Raise its slot count to add more.",
                    role=role.name, event=role.event_id.name, n=role.slot_count))

    # ------------------------------------------------------------------
    # Mail
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        template = self.env.ref(
            "event_volunteer.mail_template_volunteer_signup",
            raise_if_not_found=False)
        if template:
            for rec in records.filtered(lambda r: r.state in _ACTIVE_STATES):
                template.send_mail(rec.id, force_send=False)
        return records

    def action_portal_withdraw(self):
        """Member pulls out of a role they signed up for (portal path)."""
        for rec in self:
            if rec.state == "cancelled":
                continue
            rec.write({"state": "cancelled"})
            rec.message_post(body=_("Withdrew from this role."))
        return True

    # ------------------------------------------------------------------
    # Reminder cron
    # ------------------------------------------------------------------
    @api.model
    def _reminder_lead_days(self):
        param = self.env["ir.config_parameter"].sudo().get_param(
            "event_volunteer.reminder_lead_days", "2")
        try:
            return max(int(param), 0)
        except (TypeError, ValueError):
            return 2

    @api.model
    def _cron_send_volunteer_reminders(self):
        now = fields.Datetime.now()
        due = self.search([
            ("state", "=", "confirmed"),
            ("reminder_sent", "=", False),
            ("event_date_begin", ">=", now),
            ("event_date_begin", "<=", now + timedelta(days=self._reminder_lead_days())),
        ])
        template = self.env.ref(
            "event_volunteer.mail_template_volunteer_reminder",
            raise_if_not_found=False)
        if not template or not due:
            return
        for rec in due:
            template.send_mail(rec.id, force_send=False)
        due.write({"reminder_sent": True})
