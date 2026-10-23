# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessDenied
from odoo.http import request

DEFAULT_ESCALATE_THRESHOLD = 3
DEFAULT_ESCALATE_WINDOW_HOURS = 24


class ResUsers(models.Model):
    _inherit = "res.users"

    def _login(self, credential, user_agent_env):
        """Persists what core's own cooldown counter never does - every
        attempt, success or failure, so it's actually reportable instead
        of living only in a per-worker in-memory dict that's gone on
        the next restart.
        """
        ip = request.httprequest.environ.get("REMOTE_ADDR", "n/a") if request else "n/a"
        login = credential.get("login")
        try:
            auth_info = super()._login(credential, user_agent_env)
        except AccessDenied:
            self.env["security.login_attempt"].sudo().create(
                {"ip": ip, "login": login, "success": False})
            raise
        self.env["security.login_attempt"].sudo().create(
            {"ip": ip, "login": login, "success": True})
        return auth_info

    def _on_login_cooldown(self, failures, previous):
        """The method core's own docstring names as the intended
        override point for changing cooldown behavior. Core's cooldown
        is always temporary - this adds the one thing it leaves out:
        escalating a repeat offender to a permanent security.ip_rule
        block, plus a reportable security.event every time the cooldown
        actually triggers.
        """
        on_cooldown = super()._on_login_cooldown(failures, previous)
        if on_cooldown and request:
            ip = request.httprequest.environ.get("REMOTE_ADDR")
            if ip:
                self._security_record_cooldown(ip, failures)
        return on_cooldown

    def _security_record_cooldown(self, ip, failures):
        Event = self.env["security.event"].sudo()
        Event.create({
            "event_type": "login_cooldown",
            "severity": "warning",
            "source_ip": ip,
            "detail": f"Login cooldown triggered after {failures} "
                      f"failures from {ip}.",
        })
        self._security_maybe_escalate(ip)

    def _security_maybe_escalate(self, ip):
        ICP = self.env["ir.config_parameter"].sudo()
        threshold = int(ICP.get_param(
            "security_auth_guard.cooldown_escalate_threshold",
            DEFAULT_ESCALATE_THRESHOLD))
        if threshold <= 0:
            return
        window_hours = int(ICP.get_param(
            "security_auth_guard.cooldown_escalate_window_hours",
            DEFAULT_ESCALATE_WINDOW_HOURS))
        since = fields.Datetime.now() - timedelta(hours=window_hours)
        Event = self.env["security.event"].sudo()
        count = Event.search_count([
            ("event_type", "=", "login_cooldown"),
            ("source_ip", "=", ip),
            ("create_date", ">=", since),
        ])
        if count < threshold:
            return
        self.env["security.ip_rule"].sudo()._block_ip(
            ip, f"Auto-escalated: {count} cooldown triggers in "
                f"{window_hours}h.")
        Event.create({
            "event_type": "ip_blocked",
            "severity": "critical",
            "source_ip": ip,
            "detail": f"Auto-blocked after {count} cooldown triggers in "
                      f"{window_hours}h.",
        })
