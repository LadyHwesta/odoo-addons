# -*- coding: utf-8 -*-
from odoo import fields, models

from .res_users import DEFAULT_ESCALATE_THRESHOLD, DEFAULT_ESCALATE_WINDOW_HOURS
from .security_probe_hit import (
    DEFAULT_PROBE_BLOCK_HOURS, DEFAULT_PROBE_PERMANENT_AFTER, DEFAULT_PROBE_THRESHOLD)


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
        default=DEFAULT_ESCALATE_THRESHOLD,
        help="-1 turns off automatic blocking. Saving 0 or an empty value "
             "goes back to the default.")
    cooldown_escalate_window_hours = fields.Integer(
        string="Escalation window (hours)",
        config_parameter="security_auth_guard.cooldown_escalate_window_hours",
        default=DEFAULT_ESCALATE_WINDOW_HOURS)
    probe_block_threshold = fields.Integer(
        string="Probe requests before a block",
        config_parameter="security_auth_guard.probe_block_threshold",
        default=DEFAULT_PROBE_THRESHOLD,
        help="Requests for attack addresses (/.env, /wp-login.php, ../) from "
             "one address within 10 minutes before it's blocked. -1 turns "
             "this off.")
    probe_block_hours = fields.Integer(
        string="Probe block length (hours)",
        config_parameter="security_auth_guard.probe_block_hours",
        default=DEFAULT_PROBE_BLOCK_HOURS)
    probe_permanent_after = fields.Integer(
        string="Probe blocks before a permanent block",
        config_parameter="security_auth_guard.probe_permanent_after",
        default=DEFAULT_PROBE_PERMANENT_AFTER,
        help="The block that reaches this number within 30 days is "
             "permanent. -1 keeps every probe block temporary.")
    alert_phone_number = fields.Char(
        string="Critical alert SMS number",
        config_parameter="security_auth_guard.alert_phone_number",
        help="Only used if signalwire_sms/signalwire_voip is also "
             "installed - leave blank to disable SMS alerts.")
