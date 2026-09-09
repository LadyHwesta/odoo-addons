# -*- coding: utf-8 -*-
from odoo import api, fields, models


class EventEvent(models.Model):
    _inherit = "event.event"

    volunteer_role_ids = fields.One2many(
        "event.volunteer.role", "event_id", string="Volunteer Roles", copy=True)
    volunteer_assignment_ids = fields.One2many(
        "event.volunteer.assignment", "event_id", string="Volunteers")
    volunteer_slot_count = fields.Integer(
        compute="_compute_volunteer_stats", string="Volunteer Slots")
    volunteer_filled_count = fields.Integer(
        compute="_compute_volunteer_stats", string="Volunteers Signed Up")
    volunteer_understaffed = fields.Boolean(
        compute="_compute_volunteer_stats",
        help="At least one volunteer role still needs people.")

    @api.depends("volunteer_role_ids.slot_count", "volunteer_role_ids.filled_count")
    def _compute_volunteer_stats(self):
        for event in self:
            roles = event.volunteer_role_ids
            event.volunteer_slot_count = sum(roles.mapped("slot_count"))
            event.volunteer_filled_count = sum(roles.mapped("filled_count"))
            event.volunteer_understaffed = any(
                r.filled_count < r.slot_count for r in roles)

    def action_open_volunteer_assignments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Volunteers"),
            "res_model": "event.volunteer.assignment",
            "view_mode": "list,form",
            "domain": [("event_id", "=", self.id)],
            "context": {
                "default_event_id": self.id,
                "search_default_group_role": 1,
            },
        }
