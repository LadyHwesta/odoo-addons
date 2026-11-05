# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestIpRule(TransactionCase):
    def test_exact_ip_block(self):
        self.env["security.ip_rule"].create(
            {"ip_or_cidr": "203.0.113.5", "action": "block"})
        self.assertTrue(
            self.env["security.ip_rule"]._is_blocked("203.0.113.5"))
        self.assertFalse(
            self.env["security.ip_rule"]._is_blocked("203.0.113.6"))

    def test_cidr_block(self):
        self.env["security.ip_rule"].create(
            {"ip_or_cidr": "203.0.113.0/24", "action": "block"})
        self.assertTrue(
            self.env["security.ip_rule"]._is_blocked("203.0.113.200"))
        self.assertFalse(
            self.env["security.ip_rule"]._is_blocked("203.0.114.1"))

    def test_allow_wins_over_block(self):
        self.env["security.ip_rule"].create(
            {"ip_or_cidr": "203.0.113.0/24", "action": "block"})
        self.env["security.ip_rule"].create(
            {"ip_or_cidr": "203.0.113.5", "action": "allow"})
        self.assertFalse(
            self.env["security.ip_rule"]._is_blocked("203.0.113.5"))
        self.assertTrue(
            self.env["security.ip_rule"]._is_blocked("203.0.113.6"))

    def test_expired_rule_does_not_block(self):
        self.env["security.ip_rule"].create({
            "ip_or_cidr": "203.0.113.5", "action": "block",
            "expires_at": fields.Datetime.now() - timedelta(hours=1)})
        self.assertFalse(
            self.env["security.ip_rule"]._is_blocked("203.0.113.5"))

    def test_inactive_rule_does_not_block(self):
        rule = self.env["security.ip_rule"].create(
            {"ip_or_cidr": "203.0.113.5", "action": "block"})
        rule.active = False
        self.assertFalse(
            self.env["security.ip_rule"]._is_blocked("203.0.113.5"))

    def test_invalid_ip_or_cidr_rejected(self):
        with self.assertRaises(Exception):
            self.env["security.ip_rule"].create(
                {"ip_or_cidr": "not-an-ip", "action": "block"})

    def test_block_ip_extends_existing_rule_not_duplicate(self):
        IpRule = self.env["security.ip_rule"]
        IpRule._block_ip("203.0.113.9", "first reason")
        IpRule._block_ip("203.0.113.9", "second reason")
        rules = IpRule.search([("ip_or_cidr", "=", "203.0.113.9")])
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules.reason, "second reason")

    def test_ipv6_block_covers_the_whole_64(self):
        IpRule = self.env["security.ip_rule"]
        rule = IpRule._block_ip("2001:db8:1:2:aaaa::1", "test")
        self.assertEqual(rule.ip_or_cidr, "2001:db8:1:2::/64")
        self.assertTrue(IpRule._is_blocked("2001:db8:1:2:bbbb::9"))
        self.assertFalse(IpRule._is_blocked("2001:db8:1:3::1"))

    def test_ipv6_block_from_same_64_does_not_duplicate(self):
        IpRule = self.env["security.ip_rule"]
        IpRule._block_ip("2001:db8:1:2::1", "first")
        IpRule._block_ip("2001:db8:1:2::2", "second")
        rules = IpRule.search([("ip_or_cidr", "=", "2001:db8:1:2::/64")])
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules.reason, "second")

    def test_allow_for_one_address_wins_over_64_block(self):
        IpRule = self.env["security.ip_rule"]
        IpRule._block_ip("2001:db8:1:2::1", "test")
        IpRule.create({"ip_or_cidr": "2001:db8:1:2::5", "action": "allow"})
        self.assertFalse(IpRule._is_blocked("2001:db8:1:2::5"))
        self.assertTrue(IpRule._is_blocked("2001:db8:1:2::6"))

    def test_ipv4_mapped_address_is_treated_as_ipv4(self):
        IpRule = self.env["security.ip_rule"]
        rule = IpRule._block_ip("::ffff:203.0.113.20", "test")
        self.assertEqual(rule.ip_or_cidr, "203.0.113.20")
        self.assertTrue(IpRule._is_blocked("::ffff:203.0.113.20"))
        self.assertTrue(IpRule._is_blocked("203.0.113.20"))

    def test_protected_addresses_are_never_auto_blocked(self):
        IpRule = self.env["security.ip_rule"]
        for ip in ("172.68.26.59", "104.22.21.11", "2606:4700:1::1",
                   "::ffff:172.68.26.59", "127.0.0.1", "10.1.2.3",
                   "192.168.1.1", "::1", "fd00::1"):
            with self.subTest(ip=ip):
                self.assertFalse(IpRule._block_ip(ip, "test"))
                self.assertFalse(IpRule._is_blocked(ip))

    def test_protected_ranges_parameter_adds_to_the_list(self):
        IpRule = self.env["security.ip_rule"]
        self.assertFalse(IpRule._is_protected("203.0.113.30"))
        self.env["ir.config_parameter"].sudo().set_param(
            "security_auth_guard.protected_ranges",
            "203.0.113.0/24, not-a-range, 2001:db8::/32")
        self.assertTrue(IpRule._is_protected("203.0.113.30"))
        self.assertTrue(IpRule._is_protected("2001:db8::1"))
        self.assertFalse(IpRule._block_ip("203.0.113.30", "test"))

    def test_manual_rule_can_still_cover_a_protected_range(self):
        IpRule = self.env["security.ip_rule"]
        IpRule.create({"ip_or_cidr": "172.68.26.59", "action": "block"})
        self.assertTrue(IpRule._is_blocked("172.68.26.59"))
