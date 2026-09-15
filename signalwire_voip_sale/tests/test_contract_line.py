# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestContractLineMeteredBilling(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'project_id': 'pid123', 'api_token': 'tok456',
        })
        cls.subproject = cls.env['signalwire.subproject'].create({
            'name': 'Customer Subproject', 'server_id': cls.server.id,
            'account_sid': 'sub-abc', 'state': 'active',
        })
        cls.partner = cls.env['res.partner'].create({'name': 'Jane Customer'})
        cls.usage_product = cls.env.ref('signalwire_voip_sale.product_signalwire_usage')
        today = fields.Date.context_today(cls.env.user)
        cls.contract = cls.env['contract.contract'].create({
            'name': 'Test Contract', 'partner_id': cls.partner.id,
            'contract_type': 'sale', 'line_recurrence': True,
            'contract_line_ids': [(0, 0, {
                'product_id': cls.usage_product.id,
                'name': 'Metered usage', 'quantity': 1, 'price_unit': 0.0,
                'date_start': today, 'recurring_interval': 1,
                'recurring_rule_type': 'monthly', 'recurring_invoicing_type': 'post-paid',
                'is_signalwire_metered': True,
                'signalwire_subproject_id': cls.subproject.id,
            })],
        })
        cls.metered_line = cls.contract.contract_line_ids

    def test_prepare_invoice_line_computes_price_from_real_usage(self):
        with patch.object(
                type(self.subproject), '_compute_billed_usage', return_value=42.50) as mocked:
            vals = self.metered_line._prepare_invoice_line()

        mocked.assert_called_once()
        self.assertEqual(vals['price_unit'], 42.50)

    def test_prepare_invoice_line_passes_the_correct_period(self):
        with patch.object(
                type(self.subproject), '_compute_billed_usage', return_value=0.0) as mocked:
            self.metered_line._prepare_invoice_line()

        args, kwargs = mocked.call_args
        first_date, last_date = args
        self.assertEqual(first_date, self.metered_line.date_start)

    def test_non_metered_line_is_unaffected(self):
        plain_product = self.env['product.template'].create({'name': 'Plain Product'})
        contract = self.env['contract.contract'].create({
            'name': 'Plain Contract', 'partner_id': self.partner.id,
            'contract_type': 'sale', 'line_recurrence': True,
            'contract_line_ids': [(0, 0, {
                'product_id': plain_product.product_variant_id.id,
                'name': 'Flat fee', 'quantity': 1, 'price_unit': 10.0,
                'date_start': fields.Date.context_today(self.env.user),
                'recurring_interval': 1, 'recurring_rule_type': 'monthly',
                'recurring_invoicing_type': 'pre-paid',
            })],
        })
        vals = contract.contract_line_ids._prepare_invoice_line()
        self.assertEqual(vals['price_unit'], 10.0)
