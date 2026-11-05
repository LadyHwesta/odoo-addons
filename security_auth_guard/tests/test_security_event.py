# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSecurityEvent(TransactionCase):
    def test_escalate_to_block_creates_ip_rule(self):
        event = self.env["security.event"].create({
            "event_type": "anomaly", "severity": "critical",
            "source_ip": "203.0.113.42", "detail": "test",
        })
        event.action_escalate_to_block()
        self.assertEqual(event.state, "escalated")
        self.assertTrue(self.env["security.ip_rule"]._is_blocked("203.0.113.42"))

    def test_escalate_with_no_source_ip_does_not_error(self):
        event = self.env["security.event"].create({
            "event_type": "anomaly", "severity": "info", "detail": "no ip",
        })
        event.action_escalate_to_block()
        self.assertEqual(event.state, "escalated")

    def test_create_never_raises_when_signalwire_not_installed(self):
        # signalwire.phone_number isn't a real model in this harness -
        # _notify_critical must no-op cleanly, not blow up record creation.
        event = self.env["security.event"].create({
            "event_type": "anomaly", "severity": "critical",
            "source_ip": "203.0.113.1", "detail": "critical but unreachable",
        })
        self.assertTrue(event.exists())

    def test_escalate_protected_address_explains_and_blocks_nothing(self):
        event = self.env["security.event"].create({
            "event_type": "anomaly", "severity": "info",
            "source_ip": "172.68.26.59", "detail": "edge address",
        })
        with self.assertRaises(UserError):
            event.action_escalate_to_block()
        self.assertEqual(event.state, "new")
        self.assertFalse(self.env["security.ip_rule"]._is_blocked("172.68.26.59"))

    def test_mark_reviewed(self):
        event = self.env["security.event"].create({
            "event_type": "anomaly", "severity": "info", "detail": "x",
        })
        event.action_mark_reviewed()
        self.assertEqual(event.state, "reviewed")
