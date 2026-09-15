# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSaleOrderManagedOdoo(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Example Nonprofit', 'email': 'owner@example.org',
        })
        cls.shared_hosting_product = cls.env['product.template'].create({
            'name': 'Managed Odoo Hosting - Shared', 'type': 'service',
            'is_managed_odoo_hosting': True, 'managed_odoo_hosting_kind': 'shared',
        })
        cls.dedicated_hosting_product = cls.env['product.template'].create({
            'name': 'Managed Odoo Hosting - Dedicated', 'type': 'service',
            'is_managed_odoo_hosting': True, 'managed_odoo_hosting_kind': 'dedicated',
        })
        cls.app_product = cls.env['product.template'].create({
            'name': 'Managed Odoo App: Nonprofit Suite', 'type': 'service',
        })
        cls.app = cls.env['deployment.app'].create({
            'name': 'Nonprofit Suite', 'module_names': 'nonprofit_base,donation',
            'product_template_id': cls.app_product.id,
        })

    def _order(self, *product_templates):
        order = self.env['sale.order'].create({'partner_id': self.partner.id})
        for template in product_templates:
            self.env['sale.order.line'].create({
                'order_id': order.id, 'product_id': template.product_variant_id.id,
                'product_uom_qty': 1,
            })
        return order

    def test_order_with_no_hosting_line_creates_nothing(self):
        order = self._order(self.app_product)
        order.action_confirm()
        self.assertFalse(self.env['deployment.instance'].search(
            [('partner_id', '=', self.partner.id)]))

    def test_shared_hosting_reuses_the_existing_shared_server(self):
        shared_server = self.env['deployment.server'].create({
            'name': 'Shared Server', 'kind': 'shared',
        })
        order = self._order(self.shared_hosting_product)

        order.action_confirm()

        instance = self.env['deployment.instance'].search(
            [('partner_id', '=', self.partner.id)])
        self.assertEqual(len(instance), 1)
        self.assertEqual(instance.server_id, shared_server)
        self.assertEqual(instance.state, 'requested')

    def test_shared_hosting_without_a_shared_server_raises(self):
        order = self._order(self.shared_hosting_product)
        with self.assertRaises(UserError):
            order.action_confirm()

    def test_dedicated_hosting_creates_a_new_server(self):
        order = self._order(self.dedicated_hosting_product)

        order.action_confirm()

        instance = self.env['deployment.instance'].search(
            [('partner_id', '=', self.partner.id)])
        self.assertTrue(instance.server_id)
        self.assertEqual(instance.server_id.kind, 'dedicated')
        self.assertEqual(instance.server_id.partner_id, self.partner)

    def test_app_products_on_the_same_order_become_app_ids(self):
        self.env['deployment.server'].create({'name': 'Shared Server', 'kind': 'shared'})
        order = self._order(self.shared_hosting_product, self.app_product)

        order.action_confirm()

        instance = self.env['deployment.instance'].search(
            [('partner_id', '=', self.partner.id)])
        self.assertIn(self.app, instance.app_ids)

    def test_admin_email_and_company_name_prefilled_from_partner(self):
        self.env['deployment.server'].create({'name': 'Shared Server', 'kind': 'shared'})
        order = self._order(self.shared_hosting_product)

        order.action_confirm()

        instance = self.env['deployment.instance'].search(
            [('partner_id', '=', self.partner.id)])
        self.assertEqual(instance.admin_email, 'owner@example.org')
        self.assertEqual(instance.company_name, 'Example Nonprofit')

    def test_domain_and_db_name_are_not_set_yet(self):
        self.env['deployment.server'].create({'name': 'Shared Server', 'kind': 'shared'})
        order = self._order(self.shared_hosting_product)

        order.action_confirm()

        instance = self.env['deployment.instance'].search(
            [('partner_id', '=', self.partner.id)])
        self.assertFalse(instance.domain)
        self.assertFalse(instance.db_name)
        with self.assertRaises(UserError):
            instance.action_request()

    def test_an_activity_is_scheduled_for_the_salesperson(self):
        self.env['deployment.server'].create({'name': 'Shared Server', 'kind': 'shared'})
        order = self._order(self.shared_hosting_product)

        order.action_confirm()

        instance = self.env['deployment.instance'].search(
            [('partner_id', '=', self.partner.id)])
        self.assertTrue(instance.activity_ids)
