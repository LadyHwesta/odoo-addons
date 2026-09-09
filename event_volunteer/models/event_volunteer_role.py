# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# Assignment states that occupy a slot.
_ACTIVE_STATES = ("draft", "confirmed")


class EventVolunteerRole(models.Model):
    _name = "event.volunteer.role"
    _description = "Event Volunteer Role"
    _order = "event_id, sequence, id"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    event_id = fields.Many2one(
        "event.event", string="Event", required=True, ondelete="cascade", index=True)
    description = fields.Text(
        help="Shown to members on the event page under this role.")
    slot_count = fields.Integer(
        string="Slots Needed", default=1,
        help="How many volunteers this role needs.")
    assignment_ids = fields.One2many(
        "event.volunteer.assignment", "role_id", string="Volunteers", copy=False)

    filled_count = fields.Integer(
        compute="_compute_counts", store=True,
        help="Volunteers signed up (pending + confirmed).")
    confirmed_count = fields.Integer(compute="_compute_counts", store=True)
    seats_available = fields.Integer(compute="_compute_counts", store=True)
    fill_state = fields.Selection(
        selection=[
            ("empty", "Nobody yet"),
            ("partial", "Partly filled"),
            ("full", "Full"),
            ("over", "Over-filled"),
        ],
        compute="_compute_counts", store=True, string="Coverage")

    _slot_count_positive = models.Constraint(
        "CHECK (slot_count >= 0)",
        "A volunteer role can't need a negative number of people.",
    )

    @api.depends("slot_count", "assignment_ids.state")
    def _compute_counts(self):
        for role in self:
            active = role.assignment_ids.filtered(lambda a: a.state in _ACTIVE_STATES)
            role.filled_count = len(active)
            role.confirmed_count = len(
                active.filtered(lambda a: a.state == "confirmed"))
            role.seats_available = max(role.slot_count - role.filled_count, 0)
            if not role.filled_count:
                role.fill_state = "empty"
            elif role.filled_count < role.slot_count:
                role.fill_state = "partial"
            elif role.filled_count == role.slot_count:
                role.fill_state = "full"
            else:
                role.fill_state = "over"

    def _assignment_for(self, partner):
        self.ensure_one()
        return self.assignment_ids.filtered(
            lambda a: a.partner_id == partner and a.state in _ACTIVE_STATES)[:1]

    def action_portal_volunteer(self, partner):
        """Sign ``partner`` up for this role (portal path). Returns the
        assignment. Raises if the role is full or the partner is already on
        it."""
        self.ensure_one()
        if not partner:
            raise UserError(_("You need to be signed in to volunteer."))
        if self._assignment_for(partner):
            raise UserError(_(
                "You're already signed up as %(role)s for %(event)s.",
                role=self.name, event=self.event_id.name))
        if self.seats_available <= 0:
            raise UserError(_(
                "The %(role)s role for %(event)s is already full.",
                role=self.name, event=self.event_id.name))
        return self.env["event.volunteer.assignment"].create({
            "role_id": self.id,
            "partner_id": partner.id,
            "state": "confirmed",
            "source": "portal",
        })
