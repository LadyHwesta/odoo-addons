# -*- coding: utf-8 -*-
import contextlib
import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

from odoo import fields, http
from odoo.exceptions import AccessDenied
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
class TestBruteForceFromProxyAddress(HttpCase):
    """Real failed logins over HTTP, from 127.0.0.1. That's what every
    visitor looks like when a proxy isn't passing on real addresses, so
    the site has to stay reachable all the way past the threshold.
    """

    def _clear_failures(self):
        getattr(self.env.registry, "_login_failures", {}).clear()

    def _fail_json(self):
        return self.url_open(
            "/web/session/authenticate",
            data=json.dumps({"jsonrpc": "2.0", "params": {
                "db": self.env.cr.dbname, "login": "admin",
                "password": "definitely-wrong"}}),
            headers={"Content-Type": "application/json"})

    def _fail_form(self):
        if not self.session:
            self.authenticate(None, None)
        return self.url_open("/web/login", data={
            "login": "admin", "password": "definitely-wrong",
            "csrf_token": http.Request.csrf_token(self)})

    def _fail_repeatedly(self, fail_login):
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param("base.login_cooldown_after", "2")
        ICP.set_param("base.login_cooldown_duration", "600")
        self._clear_failures()
        self.addCleanup(self._clear_failures)
        for _i in range(8):
            fail_login()

    def test_form_login_route(self):
        self._fail_repeatedly(self._fail_form)
        self.env.invalidate_all()
        self.assertEqual(self.env["security.login_attempt"].search_count([
            ("login", "=", "admin"), ("success", "=", False)]), 8)
        Event = self.env["security.event"]
        self.assertGreaterEqual(Event.search_count([
            ("event_type", "=", "login_cooldown"),
            ("source_ip", "=", "127.0.0.1")]), 3)
        self.assertEqual(Event.search_count([
            ("event_type", "=", "anomaly"), ("severity", "=", "critical"),
            ("source_ip", "=", "127.0.0.1")]), 1)
        self.assertFalse(self.env["security.ip_rule"].search(
            [("ip_or_cidr", "like", "127.0.0.1")]))
        self.assertEqual(self.url_open("/web/login").status_code, 200)

    def test_json_login_route(self):
        # This route rolls back on failure. Under test mode that also undoes
        # own_transaction's nested cursor, so the surviving records can't be
        # seen from here and need checking against a real server.
        self._fail_repeatedly(self._fail_json)
        self.assertEqual(self.url_open("/web/login").status_code, 200)


@tagged("post_install", "-at_install")
class TestIpv6Cooldown(TransactionCase):
    """Core's own _assert_can_auth, with only the connecting address
    faked, so rotating within a /64 is tested against the real counter.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.registry_enter_test_mode_cls()

    def setUp(self):
        super().setUp()
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param("base.login_cooldown_after", "2")
        ICP.set_param("base.login_cooldown_duration", "600")
        self.addCleanup(lambda: getattr(
            self.env.registry, "_login_failures", {}).clear())
        getattr(self.env.registry, "_login_failures", {}).clear()

    @contextlib.contextmanager
    def _from(self, ip):
        fake = MagicMock()
        fake.httprequest.remote_addr = ip
        fake.httprequest.environ = {"REMOTE_ADDR": ip}
        with patch("odoo.addons.base.models.res_users.request", fake), \
                patch("odoo.addons.security_auth_guard.models.res_users"
                      ".request", fake):
            yield

    def _attempt(self, ip, fail=True):
        """True if core refused before the login was even tried."""
        Users = self.env["res.users"].with_context(lang="en_US")
        tried = False
        with self._from(ip):
            try:
                with Users._assert_can_auth(user="x"):
                    tried = True
                    if fail:
                        raise AccessDenied()
            except AccessDenied:
                pass
        return not tried

    def test_new_address_in_same_64_stays_on_cooldown(self):
        self.assertFalse(self._attempt("2001:db8:1:2::1"))
        self.assertFalse(self._attempt("2001:db8:1:2::2"))
        self.assertTrue(self._attempt("2001:db8:1:2::3"))

    def test_different_64_has_its_own_cooldown(self):
        self._attempt("2001:db8:1:2::1")
        self._attempt("2001:db8:1:2::2")
        self.assertFalse(self._attempt("2001:db8:1:3::1"))

    def test_ipv4_addresses_stay_separate(self):
        self._attempt("203.0.113.1")
        self._attempt("203.0.113.1")
        self.assertTrue(self._attempt("203.0.113.1"))
        self.assertFalse(self._attempt("203.0.113.2"))

    def test_success_clears_the_count_for_the_64(self):
        self._attempt("2001:db8:1:2::1")
        self._attempt("2001:db8:1:2::2", fail=False)
        self._attempt("2001:db8:1:2::3")
        self.assertFalse(self._attempt("2001:db8:1:2::4"))

    def test_rotating_attacker_is_escalated_to_a_64_block(self):
        IpRule = self.env["security.ip_rule"]
        self._attempt("2001:db8:1:2::1")
        self._attempt("2001:db8:1:2::2")
        for host in range(3, 6):
            self.assertTrue(self._attempt(f"2001:db8:1:2::{host}"))
        self.assertTrue(IpRule._is_blocked("2001:db8:1:2:ffff::1"))
        self.assertFalse(IpRule._is_blocked("2001:db8:1:3::1"))


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

    def test_rotating_ipv6_events_count_as_one_source(self):
        Event = self.env["security.event"]
        for host in range(1, 3):
            Event.create({
                "event_type": "login_cooldown", "severity": "warning",
                "source_ip": f"2001:db8:9:9::{host}", "detail": "test"})
        ip = "2001:db8:9:9::3"
        self.env["res.users"]._security_maybe_escalate(ip)
        self.assertFalse(self.env["security.ip_rule"]._is_blocked(ip))
        Event.create({
            "event_type": "login_cooldown", "severity": "warning",
            "source_ip": ip, "detail": "test"})
        self.env["res.users"]._security_maybe_escalate(ip)
        self.assertTrue(self.env["security.ip_rule"]._is_blocked(ip))

    def test_other_64_does_not_add_to_the_count(self):
        Event = self.env["security.event"]
        for host in range(1, 4):
            Event.create({
                "event_type": "login_cooldown", "severity": "warning",
                "source_ip": f"2001:db8:9:a::{host}", "detail": "test"})
        ip = "2001:db8:9:b::1"
        self.env["res.users"]._security_maybe_escalate(ip)
        self.assertFalse(self.env["security.ip_rule"]._is_blocked(ip))

    def test_protected_address_reports_once_and_is_not_blocked(self):
        ip = "172.68.26.59"
        Event = self.env["security.event"]
        for _i in range(3):
            Event.create({
                "event_type": "login_cooldown", "severity": "warning",
                "source_ip": ip, "detail": "test"})
        self.env["res.users"]._security_maybe_escalate(ip)
        self.env["res.users"]._security_maybe_escalate(ip)
        self.assertFalse(self.env["security.ip_rule"]._is_blocked(ip))
        self.assertEqual(Event.search_count(
            [("event_type", "=", "anomaly"), ("source_ip", "=", ip)]), 1)
        self.assertFalse(Event.search_count(
            [("event_type", "=", "ip_blocked"), ("source_ip", "=", ip)]))
