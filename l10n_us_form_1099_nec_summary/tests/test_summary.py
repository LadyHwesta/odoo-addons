# -*- coding: utf-8 -*-
from datetime import date

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class Test1099NecSummary(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        nec = cls.env.ref('l10n_us_form_1099.1099_type_nec')
        us = cls.env.ref('base.us')
        cls.contractor = cls.env['res.partner'].create({
            'name': 'Robin Sales LLC', 'is_1099': True, 'type_1099_id': nec.id,
            'vat': '12-3456789', 'street': '1 Main St', 'city': 'Austin',
            'state_id': cls.env.ref('base.state_us_44').id, 'zip': '78701', 'country_id': us.id})
        cls.no_tin = cls.env['res.partner'].create({
            'name': 'Sam Support', 'is_1099': True, 'type_1099_id': nec.id})
        cls.not_1099 = cls.env['res.partner'].create({'name': 'Office Supplies Inc'})
        cls.bank = cls.company_data['default_journal_bank']
        cls.card = cls.bank.copy({'name': 'Card payments', 'code': 'CARD', 'reported_on_1099k': True})

    def _pay(self, partner, amount, day, journal=None, post=True, payment_type='outbound'):
        payment = self.env['account.payment'].create({
            'partner_id': partner.id, 'amount': amount, 'date': day,
            'payment_type': payment_type, 'partner_type': 'supplier',
            'journal_id': (journal or self.bank).id})
        if post:
            payment.action_post()
        return payment

    def _summary(self, year):
        summary = self.env['form.1099.nec.summary'].create({'year': year})
        summary.action_compute()
        return summary

    def test_totals_only_sent_completed_payments(self):
        self._pay(self.contractor, 1500, date(2026, 3, 1))
        self._pay(self.contractor, 900, date(2026, 9, 1))
        self._pay(self.contractor, 5000, date(2026, 10, 1), post=False)
        self._pay(self.contractor, 300, date(2026, 10, 2), payment_type='inbound')
        self._pay(self.contractor, 700, date(2026, 11, 1), journal=self.card)
        self._pay(self.contractor, 999, date(2025, 12, 31))
        self._pay(self.not_1099, 9000, date(2026, 5, 1))
        line = self._summary(2026).line_ids
        self.assertEqual(line.vendor_id, self.contractor)
        self.assertAlmostEqual(line.amount, 2400.0)
        self.assertEqual(line.payment_count, 2)

    def test_threshold_by_year(self):
        self.assertEqual(self.env['form.1099.nec.summary'].create({'year': 2025}).threshold, 600.0)
        self.assertEqual(self.env['form.1099.nec.summary'].create({'year': 2026}).threshold, 2000.0)
        self.env['ir.config_parameter'].sudo().set_param('l10n_us_1099_nec.threshold.2027', '2050')
        self.assertEqual(self.env['form.1099.nec.summary'].create({'year': 2027}).threshold, 2050.0)

    def test_1500_needs_a_form_in_2025_but_not_2026(self):
        self._pay(self.contractor, 1500, date(2025, 6, 1))
        self._pay(self.contractor, 1500, date(2026, 6, 1))
        self.assertTrue(self._summary(2025).line_ids.must_file)
        self.assertFalse(self._summary(2026).line_ids.must_file)

    def test_missing_tin_and_address_are_flagged(self):
        self._pay(self.no_tin, 2500, date(2026, 6, 1))
        line = self._summary(2026).line_ids
        self.assertIn('taxpayer ID', line.issues)
        self.assertIn('address', line.issues)

    def test_statement_masks_the_tin(self):
        self._pay(self.contractor, 2500, date(2026, 6, 1))
        line = self._summary(2026).line_ids
        html = self.env['ir.actions.report']._render_qweb_html(
            'l10n_us_form_1099_nec_summary.report_1099_nec_statement', line.ids)[0].decode()
        self.assertIn('$2,500.00', html)
        self.assertIn('***-**-6789', html)
        self.assertNotIn('12-3456789', html)
        self.assertIn('Copy B', html)

    def test_nothing_to_print_below_threshold(self):
        self._pay(self.contractor, 100, date(2026, 6, 1))
        with self.assertRaises(UserError):
            self._summary(2026).action_print_statements()
