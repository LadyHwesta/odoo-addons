# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    equipment_loan_default_days = fields.Integer(
        string="Default loan length (days)",
        config_parameter="club_equipment_loan.default_days",
        default=14,
        help="Pre-fills a new loan's due date this many days after checkout.")
