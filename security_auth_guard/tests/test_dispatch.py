# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.tests import HttpCase, TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDispatchBlock(HttpCase):
    """The HttpCase test client always connects as 127.0.0.1, which lets
    this exercise the real ir.http._dispatch wiring end to end without
    faking X-Forwarded-For/proxy_mode - 127.0.0.1 IS the real connecting
    IP here. Blocking the test runner's own IP is inherently risky if a
    cleanup is missed (every later request in the suite would also be
    blocked), so the block is always removed via addCleanup, registered
    before the blocking assertion runs.
    """

    def test_blocked_ip_gets_403(self):
        rule = self.env["security.ip_rule"].create(
            {"ip_or_cidr": "127.0.0.1/32", "action": "block"})
        self.addCleanup(rule.unlink)
        response = self.url_open("/web/login")
        self.assertEqual(response.status_code, 403)

    def test_unblocked_ip_is_not_affected(self):
        response = self.url_open("/web/login")
        self.assertEqual(response.status_code, 200)

    def test_block_then_allow_override_restores_access(self):
        block = self.env["security.ip_rule"].create(
            {"ip_or_cidr": "127.0.0.1/32", "action": "block"})
        self.addCleanup(block.unlink)
        allow = self.env["security.ip_rule"].create(
            {"ip_or_cidr": "127.0.0.1", "action": "allow"})
        self.addCleanup(allow.unlink)
        response = self.url_open("/web/login")
        self.assertEqual(response.status_code, 200)


@tagged("post_install", "-at_install")
class TestCooldownEscalation(TransactionCase):
    """_security_maybe_escalate itself takes a plain IP string and
    doesn't touch `request` at all - tested directly here rather than
    via real repeated HTTP brute-forcing (slow, and would risk the same
    self-lockout concern as above for no extra coverage).
    """

    def test_escalates_after_threshold_events_in_window(self):
        ip = "203.0.113.77"
        Event = self.env["security.event"]
        for _i in range(3):
            Event.create({
                "event_type": "login_cooldown", "severity": "warning",
                "source_ip": ip, "detail": "test cooldown"})
        self.env["res.users"]._security_maybe_escalate(ip)
        self.assertTrue(self.env["security.ip_rule"]._is_blocked(ip))

    def test_does_not_escalate_below_threshold(self):
        ip = "203.0.113.78"
        self.env["security.event"].create({
            "event_type": "login_cooldown", "severity": "warning",
            "source_ip": ip, "detail": "only one"})
        self.env["res.users"]._security_maybe_escalate(ip)
        self.assertFalse(self.env["security.ip_rule"]._is_blocked(ip))

    def test_escalation_disabled_when_threshold_is_zero(self):
        ip = "203.0.113.79"
        self.env["ir.config_parameter"].sudo().set_param(
            "security_auth_guard.cooldown_escalate_threshold", "0")
        Event = self.env["security.event"]
        for _i in range(10):
            Event.create({
                "event_type": "login_cooldown", "severity": "warning",
                "source_ip": ip, "detail": "test cooldown"})
        self.env["res.users"]._security_maybe_escalate(ip)
        self.assertFalse(self.env["security.ip_rule"]._is_blocked(ip))

    def test_old_events_outside_window_do_not_count(self):
        ip = "203.0.113.80"
        Event = self.env["security.event"]
        old_date = fields.Datetime.now() - timedelta(hours=48)
        events = Event.create([
            {"event_type": "login_cooldown", "severity": "warning",
             "source_ip": ip, "detail": "old"}
            for _i in range(3)])
        # create_date is a protected, ORM-managed column - write() to it
        # is silently blocked at runtime (only settable via an XML data
        # record's own eval= during install). Backdating it for this
        # test needs a direct SQL update, then a cache invalidation so
        # the ORM re-reads the new value instead of the stale cached one.
        self.env.cr.execute(
            "UPDATE security_event SET create_date = %s WHERE id IN %s",
            (old_date, tuple(events.ids)))
        events.invalidate_recordset(["create_date"])
        self.env["res.users"]._security_maybe_escalate(ip)
        self.assertFalse(self.env["security.ip_rule"]._is_blocked(ip))
