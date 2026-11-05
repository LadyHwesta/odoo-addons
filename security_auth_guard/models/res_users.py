# -*- coding: utf-8 -*-
import collections
import contextlib
from datetime import datetime, timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessDenied
from odoo.http import request

from .security_ip_rule import block_target, own_transaction

DEFAULT_ESCALATE_THRESHOLD = 20
DEFAULT_ESCALATE_WINDOW_HOURS = 24


class _FailuresBySource(collections.defaultdict):
    """Core's failure counter, keyed by block_target instead of the exact
    address, so core's own cooldown logic applies to a whole IPv6 /64.
    """

    def __getitem__(self, key):
        return super().__getitem__(block_target(key))

    def __setitem__(self, key, value):
        super().__setitem__(block_target(key), value)

    def pop(self, key, *default):
        return super().pop(block_target(key), *default)


def _no_failures():
    return (0, datetime.min)


class ResUsers(models.Model):
    _inherit = "res.users"

    @contextlib.contextmanager
    def _assert_can_auth(self, user=None):
        """Core's check, unchanged, with its counter swapped for one that
        treats an IPv6 /64 as a single source.
        """
        registry = self.env.registry
        failures = getattr(registry, "_login_failures", None)
        if not isinstance(failures, _FailuresBySource):
            registry._login_failures = _FailuresBySource(_no_failures)
        with super()._assert_can_auth(user=user):
            yield

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
            # Its own transaction: this error rolls back the request's
            # transaction on routes like /web/session/authenticate.
            with own_transaction(self.env) as env:
                env["security.login_attempt"].create(
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
        # Its own transaction: core raises AccessDenied right after this,
        # which can roll back the request's transaction (see _login).
        with own_transaction(self.env) as env:
            env["security.event"].create({
                "event_type": "login_cooldown",
                "severity": "warning",
                "source_ip": ip,
                "detail": f"Login cooldown triggered after {failures} "
                          f"failures from {ip}.",
            })
            env["res.users"]._security_maybe_escalate(ip)

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
        count = Event._count_from_source("login_cooldown", ip, since)
        if count < threshold:
            return
        rule = self.env["security.ip_rule"].sudo()._block_ip(
            ip, f"Auto-escalated: {count} cooldown triggers in "
                f"{window_hours}h.")
        if not rule:
            self._security_report_refused_block(ip, count, since)
            return
        Event.create({
            "event_type": "ip_blocked",
            "severity": "critical",
            "source_ip": ip,
            "detail": f"Auto-blocked {rule.ip_or_cidr} after {count} "
                      f"cooldown triggers in {window_hours}h.",
        })

    def _security_report_refused_block(self, ip, count, since):
        """A proxy or private address reaching the threshold usually means
        the proxy has stopped passing on real visitor addresses, so raise
        it once per window rather than on every further attempt.
        """
        Event = self.env["security.event"].sudo()
        if Event._count_from_source("anomaly", ip, since):
            return
        Event.create({
            "event_type": "anomaly",
            "severity": "critical",
            "source_ip": ip,
            "detail": f"{ip} reached the auto-block threshold ({count} "
                      f"cooldown triggers) but is a proxy or private "
                      f"address, so it was not blocked. Check that the "
                      f"proxy is passing on real visitor addresses.",
        })
