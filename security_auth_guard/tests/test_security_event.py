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


@tagged("post_install", "-at_install")
class TestWhatNeedsAttention(TransactionCase):
    """Automatic blocks are Info (counted, charted, cleaned up); only what a
    person should look at stays Warning/Critical."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # _security_record_cooldown writes in its own transaction.
        cls.registry_enter_test_mode_cls()
        cls.Event = cls.env["security.event"]

    def _cooldown_from(self, ip, login):
        self.env["security.login_attempt"].create(
            {"ip": ip, "login": login, "success": False})
        self.env["res.users"]._security_record_cooldown(ip, 5)
        return self.Event.search(
            [("event_type", "=", "login_cooldown"), ("source_ip", "=", ip)], limit=1)

    def test_guessing_a_real_login_needs_attention(self):
        event = self._cooldown_from("203.0.113.60", "admin")
        self.assertEqual(event.severity, "warning")
        self.assertEqual(event.login, "admin")
        self.assertIn("existing user", event.detail)

    def test_bots_trying_made_up_names_are_info(self):
        event = self._cooldown_from("203.0.113.61", "wp-admin-bot")
        self.assertEqual(event.severity, "info")
        self.assertEqual(event.login, "wp-admin-bot")

    def test_old_info_events_are_cleaned_up_but_never_the_rest(self):
        old_info, old_warning, new_info = self.Event.create([
            {"event_type": "probe_blocked", "severity": "info", "detail": "old"},
            {"event_type": "anomaly", "severity": "critical", "detail": "old"},
            {"event_type": "probe_blocked", "severity": "info", "detail": "new"},
        ])
        self.env.cr.execute(
            "UPDATE security_event SET create_date = now() - interval '120 days' WHERE id IN %s",
            ((old_info.id, old_warning.id),))
        self.Event.invalidate_model(["create_date"])
        self.Event._gc_info_events()
        self.assertFalse(old_info.exists())
        self.assertTrue(old_warning.exists())
        self.assertTrue(new_info.exists())

    def test_minus_one_keeps_info_events(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "security_auth_guard.info_event_retention_days", "-1")
        event = self.Event.create(
            {"event_type": "probe_blocked", "severity": "info", "detail": "old"})
        self.env.cr.execute(
            "UPDATE security_event SET create_date = now() - interval '400 days' WHERE id = %s",
            (event.id,))
        self.Event._gc_info_events()
        self.assertTrue(event.exists())

    def test_existing_events_are_converted(self):
        import importlib.util
        from pathlib import Path
        path = Path(__file__).parent.parent / "migrations" / "19.0.1.4.0" / "post-migrate.py"
        spec = importlib.util.spec_from_file_location("sag_migrate_140", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        knock, probe, auto, cooldown, bank = self.Event.create([
            {"event_type": "ip_blocked", "severity": "warning", "source_ip": "203.0.113.70",
             "detail": "Request(s) from 203.0.113.70 refused by an active security.ip_rule."},
            {"event_type": "probe_blocked", "severity": "warning", "detail": "Blocked x"},
            {"event_type": "ip_blocked", "severity": "critical", "detail": "Auto-blocked x"},
            {"event_type": "login_cooldown", "severity": "warning", "detail": "old"},
            {"event_type": "anomaly", "severity": "critical", "detail": "bank account changed"},
        ])
        module.migrate(self.env.cr, "19.0.1.3.1")
        self.Event.invalidate_model()
        self.assertEqual((knock.event_type, knock.severity), ("request_refused", "info"))
        self.assertEqual(probe.severity, "info")
        self.assertEqual(auto.severity, "info")
        self.assertEqual(cooldown.severity, "info")
        self.assertEqual(bank.severity, "critical")

    def test_attention_filter_matches_the_dashboard_list(self):
        action = self.env.ref("security_auth_guard.security_event_action")
        self.assertIn("search_default_attention", action.context)
        blocks = self.env.ref("security_auth_guard.security_event_blocks_action")
        self.assertTrue(blocks.view_mode.startswith("graph"))
