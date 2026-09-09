# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    uls_lookup_enabled = fields.Boolean(
        string="FCC call-sign lookup",
        config_parameter="club_amateur_radio.uls_lookup_enabled",
        default=True,
        help="Allow 'Look up call sign' and the nightly licence refresh to "
             "query callook.info. Turn off for an air-gapped install.")
    ham_license_warn_days = fields.Integer(
        string="Licence expiry warning window (days)",
        config_parameter="club_amateur_radio.license_warn_days",
        default=60,
        help="A member's licence counts as 'expiring soon', and the nightly "
             "sweep raises a To-Do, once it is within this many days of "
             "expiry (or already expired).")
