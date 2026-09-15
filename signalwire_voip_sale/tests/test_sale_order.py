# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSaleOrderVoipNumberLines(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'project_id': 'pid123', 'api_token': 'tok456',
        })
        cls.product = cls.env['product.template'].create({
            'name': 'VoIP Number', 'type': 'service',
            'is_voip_number': True, 'signalwire_server_id': cls.server.id,
            'list_price': 5.0,
        })
        cls.partner = cls.env['res.partner'].create({'name': 'Jane Customer'})
        cls.order = cls.env['sale.order'].create({'partner_id': cls.partner.id})

    def setUp(self):
        super().setUp()
        self.signalwire_client = MagicMock()
        patcher = patch(
            'odoo.addons.signalwire_voip.models.signalwire_server.'
            'SignalWireServer._get_client', return_value=self.signalwire_client)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.signalwire_client.compat_post.side_effect = [
            {'sid': 'sub-abc'},  # subproject provisioning
            {'sid': 'pn-123', 'phone_number': '+12084449665'},  # number purchase
        ]
        self.signalwire_client.project_post.return_value = {
            'id': 'tok-1', 'token': 'swapi_realsecret',
        }

    def _add_number_line(self, phone_number):
        return self.order.with_context(skip_cart_verification=True)._cart_add(
            product_id=self.product.product_variant_id.id, quantity=1,
            signalwire_phone_number=phone_number,
        )

    def test_two_numbers_stay_on_separate_lines(self):
        self._add_number_line('+12084449665')
        self._add_number_line('+13052808277')
        self.assertEqual(len(self.order.order_line), 2)

    def test_adding_the_same_number_again_does_not_duplicate_the_line(self):
        first = self._add_number_line('+12084449665')
        second = self._add_number_line('+12084449665')
        self.assertEqual(first['line_id'], second['line_id'])
        self.assertEqual(len(self.order.order_line), 1)

    def test_line_gets_the_products_normal_price(self):
        result = self._add_number_line('+12084449665')
        line = self.order.order_line.filtered(lambda l: l.id == result['line_id'])
        self.assertEqual(line.price_unit, 5.0)

    def test_confirming_the_order_purchases_the_number(self):
        self._add_number_line('+12084449665')
        self.order.action_confirm()

        purchase_call = self.signalwire_client.compat_post.call_args_list[1]
        self.assertEqual(purchase_call.args[0], 'Accounts/sub-abc/IncomingPhoneNumbers.json')
        self.assertEqual(purchase_call.kwargs['PhoneNumber'], '+12084449665')

    def test_confirming_creates_a_subproject_for_the_customer(self):
        self._add_number_line('+12084449665')
        self.order.action_confirm()

        subproject = self.env['signalwire.subproject'].search(
            [('partner_id', '=', self.partner.id)])
        self.assertTrue(subproject)
        self.assertEqual(subproject.account_sid, 'sub-abc')
        self.assertEqual(subproject.state, 'active')

    def test_confirming_issues_a_customer_access_token(self):
        self._add_number_line('+12084449665')
        self.order.action_confirm()

        subproject = self.env['signalwire.subproject'].search(
            [('partner_id', '=', self.partner.id)])
        self.assertTrue(subproject.customer_token_ids)

    def test_confirming_creates_a_two_line_contract(self):
        self._add_number_line('+12084449665')
        self.order.action_confirm()

        contract = self.env['contract.contract'].search(
            [('partner_id', '=', self.partner.id)])
        self.assertEqual(len(contract), 1)
        self.assertEqual(len(contract.contract_line_ids), 2)

        rental = contract.contract_line_ids.filtered(lambda line_: not line_.is_signalwire_metered)
        usage = contract.contract_line_ids.filtered('is_signalwire_metered')
        self.assertEqual(rental.price_unit, 5.0)
        self.assertEqual(rental.recurring_invoicing_type, 'pre-paid')
        self.assertEqual(usage.recurring_invoicing_type, 'post-paid')
        self.assertTrue(usage.signalwire_subproject_id)

    def test_reusing_an_existing_active_subproject_for_a_second_number(self):
        self.signalwire_client.compat_post.side_effect = [
            {'sid': 'sub-abc'},
            {'sid': 'pn-1', 'phone_number': '+12084449665'},
            {'sid': 'pn-2', 'phone_number': '+13052808277'},
        ]
        self._add_number_line('+12084449665')
        self.order.action_confirm()

        second_order = self.env['sale.order'].create({'partner_id': self.partner.id})
        second_order.with_context(skip_cart_verification=True)._cart_add(
            product_id=self.product.product_variant_id.id, quantity=1,
            signalwire_phone_number='+13052808277')
        second_order.action_confirm()

        subprojects = self.env['signalwire.subproject'].search(
            [('partner_id', '=', self.partner.id)])
        self.assertEqual(len(subprojects), 1)
