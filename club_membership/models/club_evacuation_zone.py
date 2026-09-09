# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ClubEvacuationZone(models.Model):
    _name = "club.evacuation.zone"
    _description = "Club Evacuation / Emergency Zone"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(help="Short label used on rosters and net lists.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    coordinator_id = fields.Many2one(
        "res.partner", string="Zone Coordinator",
        help="The member who leads check-ins for this zone.")
    note = fields.Text()
    member_ids = fields.One2many("res.partner", "evacuation_zone_id", string="Members")
    member_count = fields.Integer(compute="_compute_member_count")

    _code_unique = models.Constraint(
        "unique(code)", "That evacuation zone code is already in use.")

    @api.depends("member_ids")
    def _compute_member_count(self):
        counts = dict(self.env["res.partner"]._read_group(
            [("evacuation_zone_id", "in", self.ids)],
            groupby=["evacuation_zone_id"], aggregates=["__count"]))
        for zone in self:
            zone.member_count = counts.get(zone, 0)

    @api.depends("name", "code")
    def _compute_display_name(self):
        for zone in self:
            zone.display_name = (
                "%s (%s)" % (zone.name, zone.code) if zone.code else zone.name)

    def action_view_members(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Members - %s", self.display_name),
            "res_model": "res.partner",
            "view_mode": "list,form",
            "domain": [("evacuation_zone_id", "=", self.id)],
            "context": {"default_evacuation_zone_id": self.id},
        }
