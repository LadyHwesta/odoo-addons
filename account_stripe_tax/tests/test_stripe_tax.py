# -*- coding: utf-8 -*-
import re
from unittest.mock import MagicMock, patch

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

POST = 'odoo.addons.account_stripe_tax.models.stripe_tax_client.requests.post'


class FakeStripe:
    """Answers like Stripe's Tax API: 9.25% in California, 0 elsewhere."""

    def __init__(self, rate='9.25', fail_on=None):
        self.rate, self.fail_on, self.calls = rate, fail_on, []

    def __call__(self, url, data=None, headers=None, timeout=None):
        endpoint = url.rsplit('/v1/', 1)[1]
        self.calls.append((endpoint, data))
        response = MagicMock()
        if self.fail_on and endpoint == self.fail_on:
            response.status_code = 400
            response.json.return_value = {'error': {'message': 'Stripe said no'}}
            return response
        response.status_code = 200
        if endpoint == 'tax/calculations':
            in_ca = data.get('customer_details[address][state]') == 'CA'
            exempt = data.get('customer_details[taxability_override]') == 'customer_exempt'
            rate = self.rate if in_ca and not exempt else '0.0'
            items, total_tax, i = [], 0, 0
            while f'line_items[{i}][amount]' in data:
                amount = data[f'line_items[{i}][amount]']
                tax = round(amount * float(rate) / 100)
                total_tax += tax
                items.append({
                    'reference': data[f'line_items[{i}][reference]'], 'amount': amount,
                    'amount_tax': tax,
                    'tax_breakdown': [{'amount': tax, 'tax_rate_details': {'percentage_decimal': rate}}],
                })
                i += 1
            response.json.return_value = {
                'id': f'taxcalc_{len(self.calls)}', 'tax_amount_exclusive': total_tax,
                'line_items': {'data': items}}
        elif endpoint == 'tax/transactions/create_from_calculation':
            response.json.return_value = {'id': f"tax_tx_{data['calculation']}"}
        elif endpoint == 'tax/transactions/create_reversal':
            response.json.return_value = {'id': f"tax_rev_{len(self.calls)}"}
        return response

    def endpoints(self):
        return [endpoint for endpoint, _data in self.calls]


@tagged('post_install', '-at_install')
class TestStripeTax(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        us = cls.env.ref('base.us')
        cls.provider = cls.env['payment.provider'].create({
            'name': 'Stripe', 'code': 'stripe', 'state': 'test',
            'stripe_secret_key': 'sk_test_x', 'stripe_publishable_key': 'pk_test_x',
            'company_id': cls.env.company.id,
        })
        cls.tax_account = cls.company_data['default_account_tax_sale']
        cls.env.company.write({
            'stripe_tax_provider_id': cls.provider.id,
            'stripe_tax_account_id': cls.tax_account.id,
        })
        cls.saas = cls.env['product.product'].create({
            'name': 'Managed Odoo', 'type': 'service', 'lst_price': 100.0,
            'stripe_tax_code': 'txcd_10103001', 'taxes_id': [Command.clear()],
        })
        cls.domain = cls.env['product.product'].create({
            'name': 'Domain', 'type': 'service', 'lst_price': 20.0, 'taxes_id': [Command.clear()],
        })
        cls.ca_customer = cls.env['res.partner'].create({
            'name': 'Santa Rosa Customer', 'street': '1 Main St', 'city': 'Santa Rosa',
            'state_id': cls.env.ref('base.state_us_5').id, 'zip': '95404', 'country_id': us.id,
        })
        cls.or_customer = cls.env['res.partner'].create({
            'name': 'Portland Customer', 'city': 'Portland', 'zip': '97201',
            'state_id': cls.env['res.country.state'].search([('country_id', '=', us.id), ('code', '=', 'OR')]).id,
            'country_id': us.id,
        })

    def setUp(self):
        super().setUp()
        self.stripe = FakeStripe()
        patcher = patch(POST, side_effect=self.stripe)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _invoice(self, partner=None, products=None):
        return self.env['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': (partner or self.ca_customer).id,
            'invoice_line_ids': [Command.create({'product_id': p.id, 'price_unit': p.lst_price,
                                                 'tax_ids': [Command.clear()]})
                                 for p in (products or self.saas)],
        })

    def test_california_invoice_gets_the_stripe_rate(self):
        invoice = self._invoice()
        invoice.action_post()
        line = invoice.invoice_line_ids
        self.assertEqual(line.tax_ids.mapped('amount'), [9.25])
        self.assertTrue(line.tax_ids.is_stripe_tax)
        self.assertAlmostEqual(invoice.amount_tax, 9.25)
        self.assertEqual(self.stripe.endpoints(),
                         ['tax/calculations', 'tax/transactions/create_from_calculation'])
        self.assertTrue(invoice.stripe_tax_transaction_id)
        tax_line = invoice.line_ids.filtered(lambda l: l.tax_line_id)
        self.assertEqual(tax_line.account_id, self.tax_account)

    def test_request_carries_address_code_and_cents(self):
        self._invoice().action_post()
        _endpoint, data = self.stripe.calls[0]
        self.assertEqual(data['customer_details[address][postal_code]'], '95404')
        self.assertEqual(data['customer_details[address][state]'], 'CA')
        self.assertEqual(data['line_items[0][amount]'], 10000)
        self.assertEqual(data['line_items[0][tax_code]'], 'txcd_10103001')
        self.assertEqual(data['expand[0]'], 'line_items.data.tax_breakdown')

    def test_tax_follows_the_invoice_date(self):
        from datetime import date, timedelta
        invoice = self._invoice()
        invoice.invoice_date = date.today() + timedelta(days=20)
        invoice.action_post()
        sent = self.stripe.calls[0][1]['tax_date']
        self.assertEqual(date.fromtimestamp(sent), invoice.invoice_date)

    def test_old_invoice_date_uses_todays_rules(self):
        from datetime import date, timedelta
        invoice = self._invoice()
        invoice.invoice_date = date.today() - timedelta(days=60)
        invoice.action_post()
        self.assertNotIn('tax_date', self.stripe.calls[0][1])

    def test_same_rate_reuses_one_tax(self):
        first, second = self._invoice(), self._invoice()
        (first | second).action_post()
        self.assertEqual(first.invoice_line_ids.tax_ids, second.invoice_line_ids.tax_ids)
        self.assertEqual(self.env['account.tax'].search_count([('is_stripe_tax', '=', True)]), 1)

    def test_products_without_a_code_are_left_alone(self):
        invoice = self._invoice(products=self.saas | self.domain)
        invoice.action_post()
        domain_line = invoice.invoice_line_ids.filtered(lambda l: l.product_id == self.domain)
        self.assertFalse(domain_line.tax_ids)
        _endpoint, data = self.stripe.calls[0]
        self.assertNotIn('line_items[1][amount]', data)

    def test_no_coded_products_means_no_call(self):
        self._invoice(products=self.domain).action_post()
        self.assertFalse(self.stripe.calls)

    def test_out_of_state_gets_no_tax_and_no_recorded_sale(self):
        invoice = self._invoice(partner=self.or_customer)
        invoice.action_post()
        self.assertFalse(invoice.invoice_line_ids.tax_ids)
        self.assertEqual(self.stripe.endpoints(), ['tax/calculations'])
        self.assertFalse(invoice.stripe_tax_transaction_id)

    def test_untaxed_sales_recorded_when_asked(self):
        self.env.company.stripe_tax_record_all = True
        invoice = self._invoice(partner=self.or_customer)
        invoice.action_post()
        self.assertTrue(invoice.stripe_tax_transaction_id)

    def test_exempt_customer(self):
        self.ca_customer.stripe_tax_exempt = True
        invoice = self._invoice()
        invoice.action_post()
        self.assertEqual(self.stripe.calls[0][1]['customer_details[taxability_override]'],
                         'customer_exempt')
        self.assertFalse(invoice.invoice_line_ids.tax_ids)

    def test_missing_zip_blocks_confirming(self):
        self.ca_customer.zip = False
        invoice = self._invoice()
        with self.assertRaisesRegex(UserError, 'ZIP'):
            invoice.action_post()
        self.assertEqual(invoice.state, 'draft')

    def test_stripe_refusing_the_calculation_blocks_confirming(self):
        self.stripe.fail_on = 'tax/calculations'
        invoice = self._invoice()
        with self.assertRaisesRegex(UserError, 'Stripe said no'):
            invoice.action_post()
        self.assertEqual(invoice.state, 'draft')

    def test_failure_to_record_never_blocks_and_can_be_retried(self):
        self.stripe.fail_on = 'tax/transactions/create_from_calculation'
        invoice = self._invoice()
        invoice.action_post()
        self.assertEqual(invoice.state, 'posted')
        self.assertTrue(invoice.stripe_tax_pending)
        self.assertTrue(invoice.activity_ids)
        self.stripe.fail_on = None
        invoice.action_stripe_tax_record()
        self.assertTrue(invoice.stripe_tax_transaction_id)
        self.assertFalse(invoice.stripe_tax_pending)
        self.assertFalse(invoice.activity_ids)

    def test_full_credit_note_reverses_fully(self):
        invoice = self._invoice()
        invoice.action_post()
        refund = invoice._reverse_moves()
        refund.action_post()
        endpoint, data = self.stripe.calls[-1]
        self.assertEqual(endpoint, 'tax/transactions/create_reversal')
        self.assertEqual(data['mode'], 'full')
        self.assertEqual(data['original_transaction'], invoice.stripe_tax_transaction_id)
        self.assertTrue(refund.stripe_tax_reversal_id)

    def test_partial_credit_note_reverses_its_total(self):
        invoice = self._invoice()
        invoice.action_post()
        refund = invoice._reverse_moves()
        refund.invoice_line_ids.price_unit = 50.0
        refund.action_post()
        _endpoint, data = self.stripe.calls[-1]
        self.assertEqual(data['mode'], 'partial')
        self.assertEqual(data['flat_amount'], -round(refund.amount_total * 100))

    def test_reset_to_draft_reverses_and_reconfirming_records_again(self):
        invoice = self._invoice()
        invoice.action_post()
        first = invoice.stripe_tax_transaction_id
        invoice.button_draft()
        self.assertFalse(invoice.stripe_tax_transaction_id)
        self.assertEqual(self.stripe.calls[-1][0], 'tax/transactions/create_reversal')
        invoice.action_post()
        self.assertTrue(invoice.stripe_tax_transaction_id)
        self.assertNotEqual(invoice.stripe_tax_transaction_id, first)
        references = [d['reference'] for e, d in self.stripe.calls if 'reference' in d]
        self.assertEqual(len(references), len(set(references)))

    def test_stripe_tax_off_without_a_provider(self):
        self.env.company.stripe_tax_provider_id = False
        self._invoice().action_post()
        self.assertFalse(self.stripe.calls)

    def test_secret_key_sent_as_bearer(self):
        with patch(POST, side_effect=self.stripe) as post:
            self._invoice().action_post()
        self.assertEqual(post.call_args_list[0].kwargs['headers']['Authorization'], 'Bearer sk_test_x')
        self.assertNotIn('Stripe-Version', post.call_args_list[0].kwargs['headers'])
