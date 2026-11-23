# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRetainedEarnings(TransactionCase):

    def _unaffected(self, company):
        Account = self.env['account.account']
        return Account.with_company(company).search([
            *Account._check_company_domain(company), ('account_type', '=', 'equity_unaffected')])

    def test_one_current_year_earnings_account(self):
        company = self.env.company
        if not company.chart_template:
            self.skipTest('no chart of accounts')
        self.assertEqual(len(self._unaffected(company)), 1)
        self.assertEqual(company.get_unaffected_earnings_account(), self._unaffected(company))

    def test_a_new_companys_chart_is_fixed_too(self):
        company = self.env['res.company'].create({'name': 'New Shop', 'country_id': self.env.ref('base.us').id})
        self.env['account.chart.template'].try_loading('generic_coa', company, install_demo=False)
        unaffected = self._unaffected(company)
        self.assertEqual(len(unaffected), 1)
        self.assertEqual(unaffected.code, '999999')
        retained = self.env['account.account'].with_company(company).search([
            *self.env['account.account']._check_company_domain(company), ('code', '=', '999998')])
        self.assertEqual(retained.account_type, 'equity')

    def test_a_single_current_year_earnings_account_is_left_alone(self):
        company = self.env.company
        if not company.chart_template:
            self.skipTest('no chart of accounts')
        before = self._unaffected(company)
        self.env['account.account']._retype_retained_earnings(company)
        self.assertEqual(self._unaffected(company), before)
