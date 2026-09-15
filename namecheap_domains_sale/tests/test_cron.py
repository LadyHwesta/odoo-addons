# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from dateutil.relativedelta import relativedelta

from odoo.fields import Date
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRenewalCron(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.namecheap_server = cls.env['namecheap.server'].create({
            'name': 'Test Namecheap', 'api_user': 'u', 'api_key': 'k',
            'username': 'u', 'client_ip': '1.2.3.4', 'sandbox': True,
        })
        cls.product = cls.env['product.template'].create({
            'name': 'Domain Registration', 'type': 'service',
            'is_domain_registration': True,
        })
        # A bare test company has no Chart of Accounts installed - needed
        # below to build a minimal invoice by hand for the unpaid-invoice
        # test, without going through the full recurring-invoice pipeline
        # (which needs far more accounting setup than this module's own
        # logic actually depends on). A receivable account on the partner
        # is needed too - out_invoice moves auto-add a payment-term line
        # against it.
        cls.income_account = cls.env['account.account'].create({
            'name': 'Test Income', 'code': 'TINC', 'account_type': 'income',
        })
        cls.receivable_account = cls.env['account.account'].create({
            'name': 'Test Receivable', 'code': 'TREC',
            'account_type': 'asset_receivable', 'reconcile': True,
        })
        if not cls.env['account.journal'].search([('type', '=', 'sale')]):
            cls.env['account.journal'].create({
                'name': 'Test Sales Journal', 'code': 'TSALE', 'type': 'sale',
            })
        cls.partner = cls.env['res.partner'].create({
            'name': 'Jane Customer',
            'property_account_receivable_id': cls.receivable_account.id,
        })

    def setUp(self):
        super().setUp()
        self.namecheap_client = MagicMock()
        patcher = patch(
            'odoo.addons.namecheap_domains.models.namecheap_server.'
            'NamecheapServer._get_client', return_value=self.namecheap_client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _paid_up_domain(self, name, days_to_expiry):
        contract = self.env['contract.contract'].create({
            'name': f'{name} renewal', 'partner_id': self.partner.id,
            'contract_type': 'sale', 'line_recurrence': True,
            'contract_line_ids': [(0, 0, {
                'product_id': self.product.product_variant_id.id,
                'name': name, 'quantity': 1, 'price_unit': 15.0,
                'date_start': Date.context_today(self) - relativedelta(years=1),
                'recurring_interval': 1, 'recurring_rule_type': 'yearly',
                'recurring_invoicing_type': 'pre-paid',
            })],
        })
        return self.env['namecheap.domain'].create({
            'name': name, 'server_id': self.namecheap_server.id,
            'partner_id': self.partner.id, 'state': 'active',
            'contract_id': contract.id,
            'expires_on': Date.context_today(self) + relativedelta(days=days_to_expiry),
        })

    def test_renews_a_domain_within_the_lead_window(self):
        domain = self._paid_up_domain('due-soon.com', days_to_expiry=10)
        original_expiry = domain.expires_on

        self.env['namecheap.domain']._cron_renew_domains()

        self.namecheap_client.call.assert_any_call(
            'namecheap.domains.renew', DomainName='due-soon.com', Years=1)
        self.assertEqual(domain.expires_on, original_expiry + relativedelta(years=1))

    def test_does_not_renew_a_domain_far_from_expiry(self):
        self._paid_up_domain('not-due-yet.com', days_to_expiry=90)

        self.env['namecheap.domain']._cron_renew_domains()

        self.assertFalse(any(
            c.args and c.args[0] == 'namecheap.domains.renew'
            for c in self.namecheap_client.call.call_args_list))

    def test_does_not_renew_a_domain_with_an_unpaid_invoice(self):
        domain = self._paid_up_domain('unpaid.com', days_to_expiry=5)
        # Built by hand rather than via the contract's own recurring
        # invoicing pipeline - only the link _get_related_invoices()
        # actually looks for (an account.move.line's contract_line_id)
        # matters here, not a fully realistic invoice.
        self.env['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': self.partner.id,
            'invoice_line_ids': [(0, 0, {
                'name': 'unpaid.com renewal', 'quantity': 1, 'price_unit': 15.0,
                'account_id': self.income_account.id,
                'contract_line_id': domain.contract_id.contract_line_ids[:1].id,
            })],
        })

        self.env['namecheap.domain']._cron_renew_domains()

        self.assertFalse(any(
            c.args and c.args[0] == 'namecheap.domains.renew'
            for c in self.namecheap_client.call.call_args_list))

    def test_renewal_failure_does_not_raise_or_advance_expiry(self):
        domain = self._paid_up_domain('renew-fails.com', days_to_expiry=5)
        original_expiry = domain.expires_on
        self.namecheap_client.call.side_effect = Exception('boom')

        self.env['namecheap.domain']._cron_renew_domains()  # should not raise

        self.assertEqual(domain.expires_on, original_expiry)


@tagged('post_install', '-at_install')
class TestBalanceCron(TransactionCase):

    def setUp(self):
        super().setUp()
        # A fresh server per test (not shared via setUpClass) - the cron
        # under test posts chatter messages as a side effect, and these
        # two tests need to see a clean message history each time.
        self.namecheap_server = self.env['namecheap.server'].create({
            'name': 'Test Namecheap', 'api_user': 'u', 'api_key': 'k',
            'username': 'u', 'client_ip': '1.2.3.4', 'sandbox': True,
            'low_balance_threshold': 100.0,
        })

    def _mock_balance(self, available):
        client = MagicMock()
        result = MagicMock()
        result.find.return_value = MagicMock(
            get=lambda key, default=None: {
                'AvailableBalance': str(available), 'Currency': 'USD',
            }.get(key, default))
        client.call.return_value = result
        patcher = patch(
            'odoo.addons.namecheap_domains.models.namecheap_server.'
            'NamecheapServer._get_client', return_value=client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_posts_a_message_when_balance_is_low(self):
        self._mock_balance(50.0)
        self.env['namecheap.server']._cron_check_balance()
        self.assertTrue(any(
            'low' in (msg.body or '') for msg in self.namecheap_server.message_ids))

    def test_says_nothing_when_balance_is_healthy(self):
        # mail.thread already logs a "record created" note on any new
        # server, so this checks for the absence of a *low-balance*
        # message specifically, not an empty chatter altogether.
        self._mock_balance(500.0)
        self.env['namecheap.server']._cron_check_balance()
        self.assertFalse(any(
            'low' in (msg.body or '') for msg in self.namecheap_server.message_ids))
