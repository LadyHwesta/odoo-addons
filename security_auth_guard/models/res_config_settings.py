# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Core's own cooldown parameters (res.users._on_login_cooldown) -
    # exposed here so they're reachable from Settings without dev mode,
    # not duplicated.
    login_cooldown_after = fields.Integer(
        string="Login failures before cooldown",
        config_parameter="base.login_cooldown_after")
    login_cooldown_duration = fields.Integer(
        string="Cooldown duration (seconds)",
        config_parameter="base.login_cooldown_duration")
    cooldown_escalate_threshold = fields.Integer(
        string="Cooldown triggers before permanent IP block",
        config_parameter="security_auth_guard.cooldown_escalate_threshold",
        help="0 disables auto-escalation entirely.")
    cooldown_escalate_window_hours = fields.Integer(
        string="Escalation window (hours)",
        config_parameter="security_auth_guard.cooldown_escalate_window_hours")
    alert_phone_number = fields.Char(
        string="Critical alert SMS number",
        config_parameter="security_auth_guard.alert_phone_number",
        help="Only used if signalwire_sms/signalwire_voip is also "
             "installed - leave blank to disable SMS alerts.")
