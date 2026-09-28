# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo.fields import Date
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestAccountReminderStage(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.template = cls.env["mail.template"].create({
            "name": "Test Reminder Template",
            "model_id": cls.env.ref("account.model_account_move").id,
            "subject": "Test reminder for {{ object.name }}",
            "body_html": "<p>Test reminder</p>",
        })
        cls.Stage = cls.env["account.reminder.stage"]

    def _make_invoice(self, due_date, partner=None):
        invoice = self._create_invoice(partner_id=(partner or self.partner_a).id, post=True)
        invoice.invoice_date_due = due_date
        return invoice

    def _make_stage(self, days_offset, name="Test Stage"):
        return self.Stage.create({
            "name": name,
            "days_offset": days_offset,
            "mail_template_id": self.template.id,
        })

    def test_before_due_date_stage_fires_exactly_on_its_day(self):
        stage = self._make_stage(-3)
        today = Date.context_today(self.Stage)
        invoice = self._make_invoice(today + timedelta(days=3))
        self.Stage._cron_send_reminders()
        self.assertIn(stage, invoice.sent_reminder_stage_ids)

    def test_before_due_date_stage_does_not_fire_early(self):
        stage = self._make_stage(-3)
        today = Date.context_today(self.Stage)
        invoice = self._make_invoice(today + timedelta(days=5))
        self.Stage._cron_send_reminders()
        self.assertNotIn(stage, invoice.sent_reminder_stage_ids)

    def test_before_due_date_stage_does_not_fire_late_once_overdue(self):
        stage = self._make_stage(-3)
        today = Date.context_today(self.Stage)
        # The invoice was due 1 day ago - the -3 "heads up" window already
        # passed, so it must never fire, not even retroactively.
        invoice = self._make_invoice(today - timedelta(days=1))
        self.Stage._cron_send_reminders()
        self.assertNotIn(stage, invoice.sent_reminder_stage_ids)

    def test_overdue_stage_fires_on_its_exact_day(self):
        stage = self._make_stage(7)
        today = Date.context_today(self.Stage)
        invoice = self._make_invoice(today - timedelta(days=7))
        self.Stage._cron_send_reminders()
        self.assertIn(stage, invoice.sent_reminder_stage_ids)

    def test_overdue_stage_catches_up_if_the_cron_was_delayed(self):
        stage = self._make_stage(7)
        today = Date.context_today(self.Stage)
        # 10 days overdue, past the 7-day threshold - a delayed cron run
        # should still send it rather than skip it forever.
        invoice = self._make_invoice(today - timedelta(days=10))
        self.Stage._cron_send_reminders()
        self.assertIn(stage, invoice.sent_reminder_stage_ids)

    def test_a_stage_is_only_ever_sent_once_per_invoice(self):
        stage = self._make_stage(7)
        today = Date.context_today(self.Stage)
        invoice = self._make_invoice(today - timedelta(days=7))
        self.Stage._cron_send_reminders()
        self.Stage._cron_send_reminders()
        self.assertEqual(len(invoice.sent_reminder_stage_ids), 1)

    def test_paid_invoice_is_excluded(self):
        stage = self._make_stage(7)
        today = Date.context_today(self.Stage)
        invoice = self._make_invoice(today - timedelta(days=7))
        self._register_payment(invoice)
        self.assertEqual(invoice.payment_state, "paid")
        self.Stage._cron_send_reminders()
        self.assertNotIn(stage, invoice.sent_reminder_stage_ids)

    def test_reminder_exempt_partner_is_skipped(self):
        stage = self._make_stage(7)
        today = Date.context_today(self.Stage)
        self.partner_a.reminder_exempt = True
        invoice = self._make_invoice(today - timedelta(days=7))
        self.Stage._cron_send_reminders()
        self.assertNotIn(stage, invoice.sent_reminder_stage_ids)

    def test_stage_scoped_to_another_company_does_not_fire(self):
        other_company = self.env["res.company"].create({"name": "Other Co"})
        stage = self._make_stage(7)
        stage.company_id = other_company
        today = Date.context_today(self.Stage)
        invoice = self._make_invoice(today - timedelta(days=7))
        self.Stage._cron_send_reminders()
        self.assertNotIn(stage, invoice.sent_reminder_stage_ids)
