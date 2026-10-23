# -*- coding: utf-8 -*-
from odoo import fields, models


class SecurityLoginAttempt(models.Model):
    """Every login attempt, success or failure - core's own cooldown
    counter (res.users._assert_can_auth) tracks failures in memory only,
    lost on every restart and never queryable. This is the persisted,
    reportable record of the same events.
    """
    _name = "security.login_attempt"
    _description = "Security Login Attempt"
    _order = "occurred_at desc"

    ip = fields.Char(required=True, index=True)
    login = fields.Char(index=True)
    success = fields.Boolean()
    occurred_at = fields.Datetime(default=fields.Datetime.now, required=True)
