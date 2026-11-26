# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.tests import BaseCase, HttpCase, TransactionCase, tagged

from ..models.security_probe_hit import probe_reason


class TestProbeReason(BaseCase):

    def test_attack_addresses_are_probes(self):
        for path, query in [
            ("/.env", ""), ("/backend/.env.local", ""), ("/.git/config", ""),
            ("/wp-login.php", ""), ("/blog/wp-admin/setup-config.php", ""),
            ("/xmlrpc.php", ""), ("/phpmyadmin/", ""), ("/index.php", ""),
            ("/cgi-bin/luci", ""), ("/a/%2e%2e/%2e%2e/etc/passwd", ""),
            ("/userfiles", "path=../../../.env"),
            ("/vendor/phpunit/phpunit/src/Util/PHP/eval-stdin.php", ""),
            ("/backup.sql", ""), ("/actuator/env", ""),
        ]:
            with self.subTest(path=path, query=query):
                self.assertTrue(probe_reason(path, query))

    def test_ordinary_missing_pages_are_not(self):
        for path, query in [
            ("/", ""), ("/contactus", ""), ("/shop/old-product", ""),
            ("/.well-known/security.txt", ""), ("/environment", ""),
            ("/blog/envelopes-1", ""), ("/web/login", "redirect=/odoo"),
            # Old WordPress media links on a migrated site: real visitors.
            ("/wp-content/uploads/2019/05/field-day.jpg", ""),
            ("/wp-includes/js/jquery.js", ""),
            ("/docs/report.pdf", ""), ("/search", "q=a+b"),
        ]:
            with self.subTest(path=path, query=query):
                self.assertIsNone(probe_reason(path, query))


class TestProbeBlocking(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Hit = self.env["security.probe_hit"]
        self.IpRule = self.env["security.ip_rule"]
        self.Event = self.env["security.event"]

    def _probe(self, ip, times):
        rule = None
        for _i in range(times):
            rule = self.Hit._record(ip, "/.env", ".env") or rule
        return rule

    def test_below_the_threshold_nothing_is_blocked(self):
        self._probe("203.0.113.10", 2)
        self.assertFalse(self.IpRule._is_blocked("203.0.113.10"))

    def test_third_probe_blocks_for_a_day(self):
        rule = self._probe("203.0.113.11", 3)
        self.assertTrue(self.IpRule._is_blocked("203.0.113.11"))
        self.assertTrue(rule.expires_at)
        hours = (rule.expires_at - fields.Datetime.now()).total_seconds() / 3600
        self.assertAlmostEqual(hours, 24, delta=0.1)
        event = self.Event.search([("source_ip", "=", "203.0.113.11")])
        self.assertEqual(event.event_type, "probe_blocked")
        # A block that worked: counted and charted, not listed for review.
        self.assertEqual(event.severity, "info")
        self.assertIn("for 24h", event.detail)

    def test_one_event_per_block_however_many_probes(self):
        self._probe("203.0.113.12", 8)
        self.assertEqual(self.Event.search_count(
            [("source_ip", "=", "203.0.113.12")]), 1)

    def test_old_probes_do_not_count(self):
        hits = self.Hit.create([
            {"ip": "203.0.113.13", "source": "203.0.113.13", "path": "/.env"}
            for _i in range(2)])
        self.env.cr.execute(
            "UPDATE security_probe_hit SET create_date = %s WHERE id IN %s",
            (fields.Datetime.now() - timedelta(hours=1), tuple(hits.ids)))
        hits.invalidate_recordset(["create_date"])
        self._probe("203.0.113.13", 1)
        self.assertFalse(self.IpRule._is_blocked("203.0.113.13"))

    def test_third_block_in_thirty_days_is_permanent(self):
        ip = "203.0.113.14"
        self.Event.create([
            {"event_type": "probe_blocked", "severity": "warning",
             "source_ip": ip, "detail": "earlier"} for _i in range(2)])
        rule = self._probe(ip, 3)
        self.assertFalse(rule.expires_at)

    def test_an_expired_block_starts_again(self):
        ip = "203.0.113.15"
        old = self.IpRule.create({
            "ip_or_cidr": ip, "action": "block",
            "expires_at": fields.Datetime.now() - timedelta(hours=1)})
        rule = self._probe(ip, 3)
        self.assertEqual(rule, old)
        self.assertTrue(self.IpRule._is_blocked(ip))

    def test_a_permanent_block_is_never_shortened(self):
        ip = "203.0.113.16"
        self.IpRule._block_ip(ip, "by hand")
        rule = self.IpRule._block_ip(
            ip, "probe", expires_at=fields.Datetime.now() + timedelta(hours=1))
        self.assertFalse(rule.expires_at)

    def test_rotating_ipv6_counts_as_one_source(self):
        for host in range(1, 4):
            self.Hit._record(f"2001:db8:5:5::{host}", "/.env", ".env")
        self.assertTrue(self.IpRule._is_blocked("2001:db8:5:5::99"))

    def test_proxy_address_is_reported_not_blocked(self):
        ip = "172.68.26.59"  # Cloudflare
        self._probe(ip, 5)
        self.assertFalse(self.IpRule._is_blocked(ip))
        self.assertEqual(self.Event.search_count(
            [("source_ip", "=", ip), ("event_type", "=", "anomaly")]), 1)

    def test_turned_off(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "security_auth_guard.probe_block_threshold", "-1")
        self._probe("203.0.113.17", 10)
        self.assertFalse(self.IpRule._is_blocked("203.0.113.17"))
        self.assertFalse(self.Hit.search([("ip", "=", "203.0.113.17")]))

    def test_old_hits_are_cleaned_up(self):
        hit = self.Hit.create({"ip": "203.0.113.18", "source": "203.0.113.18"})
        self.env.cr.execute(
            "UPDATE security_probe_hit SET create_date = %s WHERE id = %s",
            (fields.Datetime.now() - timedelta(days=2), hit.id))
        hit.invalidate_recordset(["create_date"])
        self.Hit._gc_old_hits()
        self.assertFalse(hit.exists())


@tagged("post_install", "-at_install")
class TestProbeOverHttp(HttpCase):
    """The test client connects from 127.0.0.1, a protected address, so
    real probes over HTTP are counted but never block the test run.
    """

    def test_probe_still_gets_a_plain_404(self):
        for path in ("/.env", "/wp-login.php", "/a/%2e%2e/etc/passwd"):
            with self.subTest(path=path):
                self.assertEqual(self.url_open(path).status_code, 404)
        self.assertEqual(self.url_open("/web/login").status_code, 200)

    def test_blocked_address_is_refused_on_unmatched_addresses_too(self):
        rule = self.env["security.ip_rule"].create(
            {"ip_or_cidr": "127.0.0.1/32", "action": "block"})
        self.addCleanup(rule.unlink)
        self.assertEqual(self.url_open("/no-such-page").status_code, 403)
