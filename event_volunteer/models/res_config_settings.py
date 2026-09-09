# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    volunteer_reminder_lead_days = fields.Integer(
        string="Volunteer reminder lead time (days)",
        config_parameter="event_volunteer.reminder_lead_days",
        default=2,
        help="How many days before an event its confirmed volunteers get a "
             "reminder email.")
