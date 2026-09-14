# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo import Command
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSaleOrderHestiaCPProvisioning(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['hestiacp.server'].create({
            'name': 'Test Server',
            'hostname': 'https://hestia.example.com:8083',
            'access_key': 'test-access-key',
            'secret_key': 'test-secret-key',
        })
        cls.hosting_template = cls.env['product.template'].create({
            'name': 'Basic Hosting',
            'is_hosting_package': True,
            'hestiacp_server_id': cls.server.id,
            'hestiacp_package_name': 'basic',
            'list_price': 10.0,
        })
        cls.plain_template = cls.env['product.template'].create({
            'name': 'A Consulting Hour',
            'list_price': 100.0,
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'Jane Customer', 'email': 'jane@example.com',
        })

    def _mock_client(self):
        mock_client = MagicMock()
        mock_client.call.return_value = ''
        patcher = patch(
            'odoo.addons.hestiacp_hosting.models.hestiacp_server.HestiaCPServer._get_client',
            return_value=mock_client)
        patcher.start()
        self.addCleanup(patcher.stop)
        return mock_client

    def test_confirming_an_order_with_a_hosting_line_provisions_an_account(self):
        self._mock_client()
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [Command.create({
                'product_id': self.hosting_template.product_variant_id.id,
                'product_uom_qty': 1,
            })],
        })

        order.action_confirm()

        account = self.env['hestiacp.account'].search([('sale_order_id', '=', order.id)])
        self.assertEqual(len(account), 1)
        self.assertEqual(account.state, 'active')
        self.assertTrue(account.contract_id, "should have created a billing contract")
        self.assertEqual(account.contract_id.contract_line_ids.product_id,
                          self.hosting_template.product_variant_id)

    def test_confirming_an_order_without_a_hosting_line_creates_nothing(self):
        self._mock_client()
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [Command.create({
                'product_id': self.plain_template.product_variant_id.id,
                'product_uom_qty': 1,
            })],
        })

        order.action_confirm()

        account = self.env['hestiacp.account'].search([('sale_order_id', '=', order.id)])
        self.assertFalse(account)

    def test_confirming_a_mixed_order_only_provisions_the_hosting_line(self):
        self._mock_client()
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [
                Command.create({
                    'product_id': self.hosting_template.product_variant_id.id,
                    'product_uom_qty': 1,
                }),
                Command.create({
                    'product_id': self.plain_template.product_variant_id.id,
                    'product_uom_qty': 2,
                }),
            ],
        })

        order.action_confirm()

        accounts = self.env['hestiacp.account'].search([('sale_order_id', '=', order.id)])
        self.assertEqual(len(accounts), 1)
        self.assertEqual(accounts.product_id, self.hosting_template)
