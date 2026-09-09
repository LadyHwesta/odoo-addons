# -*- coding: utf-8 -*-
from datetime import date, timedelta

from psycopg2 import IntegrityError

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import HttpCase, TransactionCase, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestEquipmentLoan(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Loan = cls.env["club.equipment.loan"]
        cls.eq = cls.env["maintenance.equipment"].create({
            "name": "Yaesu FT-891", "is_loanable": True})
        cls.eq2 = cls.env["maintenance.equipment"].create({
            "name": "MFJ-259 Analyzer", "is_loanable": True})
        cls.p1 = cls.env["res.partner"].create({"name": "Dana", "email": "dana@t.com"})
        cls.p2 = cls.env["res.partner"].create({"name": "Erin", "email": "erin@t.com"})

    def _loan(self, **kw):
        return self.Loan.create(dict({
            "equipment_id": self.eq.id, "borrower_id": self.p1.id}, **kw))

    # ------------------------------------------------------------------
    def test_reference_and_due_date_defaults(self):
        loan = self._loan(checkout_date="2026-03-01")
        self.assertTrue(loan.name.startswith("LOAN/"))
        self.assertNotEqual(loan.name, "/")
        self.assertEqual(loan.due_date, date(2026, 3, 15))  # +14 default

    def test_due_date_default_days_setting(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "club_equipment_loan.default_days", "7")
        loan = self._loan(checkout_date="2026-03-01")
        self.assertEqual(loan.due_date, date(2026, 3, 8))

    def test_one_active_loan_per_item(self):
        self._loan()
        with self.assertRaises(ValidationError):
            self._loan()  # second reserved loan on the same equipment
        # a loan on a different item is fine
        self.Loan.create({"equipment_id": self.eq2.id, "borrower_id": self.p2.id})

    def test_active_loan_frees_up_after_return(self):
        first = self._loan()
        first.borrower_accepted = True
        first.action_check_out()
        first.action_check_in()
        # now a new loan on the same item is allowed
        second = self._loan(borrower_id=self.p2.id)
        self.assertEqual(second.state, "reserved")

    def test_checkout_needs_acceptance(self):
        loan = self._loan()
        with self.assertRaises(UserError):
            loan.action_check_out()
        loan.borrower_accepted = True
        loan.action_check_out()
        self.assertEqual(loan.state, "out")

    def test_full_workflow_and_return_date(self):
        loan = self._loan(borrower_accepted=True)
        loan.action_check_out()
        self.assertEqual(loan.state, "out")
        loan.action_check_in()
        self.assertEqual(loan.state, "returned")
        self.assertEqual(loan.return_date, date.today())
        self.assertFalse(loan.is_overdue)

    def test_checkout_queues_confirmation_mail(self):
        loan = self._loan(borrower_accepted=True)
        loan.action_check_out()
        mails = self.env["mail.mail"].search([
            ("model", "=", "club.equipment.loan"), ("res_id", "=", loan.id)])
        self.assertTrue(mails)

    def test_overdue_sweep(self):
        # checkout in the past so due_date can also be in the past without
        # tripping the due >= checkout CHECK constraint.
        loan = self._loan(
            borrower_accepted=True,
            checkout_date=date.today() - timedelta(days=10),
            due_date=date.today() + timedelta(days=1))
        loan.action_check_out()
        self.assertFalse(loan.is_overdue)
        loan.due_date = date.today() - timedelta(days=2)
        self.Loan._cron_flag_overdue()
        loan.invalidate_recordset()
        self.assertTrue(loan.is_overdue)
        self.assertTrue(loan.activity_ids.filtered(
            lambda a: (a.summary or "").startswith("Overdue loan")))
        mails_1 = self.env["mail.mail"].search_count([
            ("model", "=", "club.equipment.loan"), ("res_id", "=", loan.id)])
        # a second sweep doesn't re-notify
        self.Loan._cron_flag_overdue()
        mails_2 = self.env["mail.mail"].search_count([
            ("model", "=", "club.equipment.loan"), ("res_id", "=", loan.id)])
        self.assertEqual(mails_1, mails_2)

    def test_equipment_availability_compute(self):
        self.assertEqual(self.eq.loan_availability, "available")
        loan = self._loan(borrower_accepted=True)
        self.eq.invalidate_recordset()
        self.assertEqual(self.eq.loan_availability, "reserved")
        self.assertEqual(self.eq.current_loan_id, loan)
        loan.action_check_out()
        self.eq.invalidate_recordset()
        self.assertEqual(self.eq.loan_availability, "on_loan")
        loan.action_check_in()
        self.eq.invalidate_recordset()
        self.assertEqual(self.eq.loan_availability, "available")
        self.assertEqual(self.eq.loan_count, 1)

    def test_non_loanable_equipment_has_no_availability(self):
        plain = self.env["maintenance.equipment"].create({"name": "Bench PSU"})
        self.assertFalse(plain.loan_availability)

    @mute_logger("odoo.sql_db")
    def test_due_before_checkout_rejected(self):
        with self.assertRaises(IntegrityError):
            self.Loan.create({
                "equipment_id": self.eq.id, "borrower_id": self.p1.id,
                "checkout_date": "2026-01-10", "due_date": "2026-01-05"})


@tagged("post_install", "-at_install")
class TestEquipmentLoanPortal(HttpCase):
    def test_my_loans_page(self):
        portal_user = self.env["res.users"].create({
            "name": "Member Fred", "login": "fred_member", "password": "fred_member",
            "group_ids": [(6, 0, [self.env.ref("base.group_portal").id])],
        })
        eq = self.env["maintenance.equipment"].create({
            "name": "Comet Antenna", "is_loanable": True})
        self.env["club.equipment.loan"].create({
            "equipment_id": eq.id,
            "borrower_id": portal_user.partner_id.id,
            "borrower_accepted": True,
        }).action_check_out()

        self.authenticate("fred_member", "fred_member")
        resp = self.url_open("/my/loans")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Comet Antenna", resp.text)

        home = self.url_open("/my")
        self.assertEqual(home.status_code, 200)
        self.assertIn("Equipment on loan", home.text)
