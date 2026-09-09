# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    evacuation_zone_id = fields.Many2one(
        "club.evacuation.zone", string="Evacuation Zone", index="btree_not_null",
        help="Emergency / evacuation zone this member is assigned to, for "
             "net check-ins and roster call-downs.")
