# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSaleOrderDomainLines(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.us = cls.env.ref('base.us')
        cls.namecheap_server = cls.env['namecheap.server'].create({
            'name': 'Test Namecheap', 'api_user': 'u', 'api_key': 'k',
            'username': 'u', 'client_ip': '1.2.3.4', 'sandbox': True,
        })
        cls.product = cls.env['product.template'].create({
            'name': 'Domain Registration',
            'type': 'service',
            'is_domain_registration': True,
            'namecheap_server_id': cls.namecheap_server.id,
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'Jane Customer', 'street': '123 Main St', 'city': 'Springfield',
            'zip': '55555', 'country_id': cls.us.id, 'phone': '5556102107',
            'email': 'jane@example.com',
        })
        cls.order = cls.env['sale.order'].create({'partner_id': cls.partner.id})

    def setUp(self):
        super().setUp()
        self.namecheap_client = MagicMock()
        patcher = patch(
            'odoo.addons.namecheap_domains.models.namecheap_server.'
            'NamecheapServer._get_client', return_value=self.namecheap_client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _add_domain_line(self, domain_name, price=15.0, years=1):
        return self.order.with_context(skip_cart_verification=True)._cart_add(
            product_id=self.product.product_variant_id.id, quantity=1,
            namecheap_domain_name=domain_name, namecheap_years=years,
        )

    # -- cart line separation ---------------------------------------------

    def test_two_domains_stay_on_separate_lines(self):
        self._add_domain_line('one.com')
        self._add_domain_line('two.com')
        self.assertEqual(len(self.order.order_line), 2)
        domains = self.order.order_line.mapped('namecheap_domain_name')
        self.assertEqual(sorted(domains), ['one.com', 'two.com'])

    def test_adding_the_same_domain_again_does_not_duplicate_the_line(self):
        first = self._add_domain_line('one.com')
        second = self._add_domain_line('one.com')
        self.assertEqual(first['line_id'], second['line_id'])
        self.assertEqual(len(self.order.order_line), 1)

    def test_line_carries_the_domain_name_and_years(self):
        result = self._add_domain_line('example.com', years=2)
        line = self.order.order_line.filtered(lambda l: l.id == result['line_id'])
        self.assertEqual(line.namecheap_domain_name, 'example.com')
        self.assertEqual(line.namecheap_years, 2)

    def test_price_unit_write_sticks_after_cart_add(self):
        """price_unit is a computed, readonly=False field - the whole
        add-to-cart flow depends on a plain write() after _cart_add()
        actually sticking rather than getting silently recomputed away.
        """
        result = self._add_domain_line('example.com')
        line = self.order.order_line.filtered(lambda l: l.id == result['line_id'])
        line.price_unit = 42.0
        self.assertEqual(line.price_unit, 42.0)

    # -- order confirmation: real registration + renewal contract ---------

    def test_confirming_the_order_registers_the_domain(self):
        result = self._add_domain_line('example.com')
        line = self.order.order_line.filtered(lambda l: l.id == result['line_id'])
        line.price_unit = 15.0
        self.order.action_confirm()

        args, kwargs = self.namecheap_client.call.call_args
        self.assertEqual(args[0], 'namecheap.domains.create')
        self.assertEqual(kwargs['DomainName'], 'example.com')
        self.assertEqual(kwargs['RegistrantFirstName'], 'Jane')

    def test_confirming_the_order_creates_a_namecheap_domain_record(self):
        result = self._add_domain_line('example.com')
        line = self.order.order_line.filtered(lambda l: l.id == result['line_id'])
        line.price_unit = 15.0
        self.order.action_confirm()

        domain = self.env['namecheap.domain'].search([('name', '=', 'example.com')])
        self.assertTrue(domain)
        self.assertEqual(domain.sale_order_id, self.order)
        self.assertEqual(domain.partner_id, self.partner)
        self.assertTrue(domain.contract_id)

    def test_confirming_the_order_creates_a_yearly_renewal_contract_line(self):
        result = self._add_domain_line('example.com', years=3)
        line = self.order.order_line.filtered(lambda l: l.id == result['line_id'])
        line.price_unit = 45.0
        self.order.action_confirm()

        domain = self.env['namecheap.domain'].search([('name', '=', 'example.com')])
        contract_line = domain.contract_id.contract_line_ids
        self.assertEqual(contract_line.recurring_rule_type, 'yearly')
        self.assertEqual(contract_line.recurring_interval, 3)
        self.assertEqual(contract_line.price_unit, 45.0)

    def test_confirming_without_a_namecheap_server_raises(self):
        self.product.namecheap_server_id = False
        result = self._add_domain_line('example.com')
        line = self.order.order_line.filtered(lambda l: l.id == result['line_id'])
        line.price_unit = 15.0
        with self.assertRaises(UserError):
            self.order.action_confirm()
