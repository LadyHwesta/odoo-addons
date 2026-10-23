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
