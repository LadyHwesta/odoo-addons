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


@tagged("post_install", "-at_install")
class TestSettingsDefaults(TransactionCase):
    """A parameter that was never set has to show, and save, the real
    default. A 0 would quietly switch off the protection it controls.
    """

    KEYS = ("security_auth_guard.cooldown_escalate_threshold",
            "security_auth_guard.cooldown_escalate_window_hours")

    def test_saving_settings_on_a_new_install_keeps_protection_on(self):
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.search([("key", "in", self.KEYS)]).unlink()
        self.env["res.config.settings"].create({}).execute()
        self.assertEqual(
            [ICP.get_param(key) for key in self.KEYS], ["20", "24"])

    def test_saving_settings_keeps_values_already_chosen(self):
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param("security_auth_guard.cooldown_escalate_threshold", "7")
        self.env["res.config.settings"].create({}).execute()
        self.assertEqual(ICP.get_param(
            "security_auth_guard.cooldown_escalate_threshold"), "7")

    def test_settings_show_the_real_numbers_on_a_new_install(self):
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.search([("key", "in", self.KEYS)]).unlink()
        settings = self.env["res.config.settings"].create({})
        self.assertEqual(settings.cooldown_escalate_threshold, 20)
        self.assertEqual(settings.cooldown_escalate_window_hours, 24)

    def test_minus_one_turns_off_automatic_blocking(self):
        ip = "203.0.113.90"
        self.env["res.config.settings"].create(
            {"cooldown_escalate_threshold": -1}).execute()
        self.env["security.event"].create([
            {"event_type": "login_cooldown", "severity": "warning",
             "source_ip": ip, "detail": "test"} for _i in range(30)])
        self.env["res.users"]._security_maybe_escalate(ip)
        self.assertFalse(self.env["security.ip_rule"]._is_blocked(ip))
