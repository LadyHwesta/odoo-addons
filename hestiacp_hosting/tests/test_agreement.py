# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo import Command, fields
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.hestiacp_hosting.controllers.agreement import WebsiteSale
from odoo.addons.http_routing.tests.common import MockRequest


@tagged('post_install', '-at_install')
class TestHestiaCPAgreement(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.agreement = cls.env['hestiacp.agreement'].create({
            'name': 'Test Agreement',
            'version': '1.0',
            'body_html': '<p>Do not spam. Let people unsubscribe.</p>',
        })
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

    def _hosting_order(self):
        return self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [Command.create({
                'product_id': self.hosting_template.product_variant_id.id,
                'product_uom_qty': 1,
            })],
        })

    def _plain_order(self):
        return self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [Command.create({
                'product_id': self.plain_template.product_variant_id.id,
                'product_uom_qty': 1,
            })],
        })

    # -- sale.order helper -------------------------------------------------

    def test_hosting_order_requires_aup_acceptance(self):
        self.assertTrue(self._hosting_order()._hestiacp_requires_aup_acceptance())

    def test_plain_order_does_not_require_aup_acceptance(self):
        self.assertFalse(self._plain_order()._hestiacp_requires_aup_acceptance())

    # -- checkout gate (website_sale's own error-list extension point) -----

    def test_payment_is_blocked_until_the_agreement_is_accepted(self):
        order = self._hosting_order()

        # _() (used to build the error message) walks the call stack
        # looking for a bound request env, same as it would from a real
        # controller call - MockRequest supplies that outside of an
        # actual HTTP request.
        with MockRequest(self.env):
            errors = WebsiteSale()._get_shop_payment_errors(order)

        self.assertTrue(
            any('Hosting Service Agreement' in (error[0] or '') for error in errors),
            "unaccepted hosting order should block payment with an agreement error")

    def test_payment_is_not_blocked_once_the_agreement_is_accepted(self):
        order = self._hosting_order()
        order.write({
            'hestiacp_aup_agreement_id': self.agreement.id,
            'hestiacp_aup_accepted_on': fields.Datetime.now(),
            'hestiacp_aup_accepted_ip': '127.0.0.1',
        })

        with MockRequest(self.env):
            errors = WebsiteSale()._get_shop_payment_errors(order)

        self.assertFalse(
            any('Hosting Service Agreement' in (error[0] or '') for error in errors))

    def test_payment_is_not_blocked_for_an_order_without_hosting(self):
        order = self._plain_order()

        with MockRequest(self.env):
            errors = WebsiteSale()._get_shop_payment_errors(order)

        self.assertFalse(
            any('Hosting Service Agreement' in (error[0] or '') for error in errors))

    # -- provisioning copies the acceptance onto the permanent account -----

    def test_provisioning_copies_agreement_acceptance_onto_the_account(self):
        self._mock_client()
        order = self._hosting_order()
        order.write({
            'hestiacp_aup_agreement_id': self.agreement.id,
            'hestiacp_aup_accepted_on': fields.Datetime.now(),
            'hestiacp_aup_accepted_ip': '127.0.0.1',
        })

        order.action_confirm()

        account = self.env['hestiacp.account'].search([('sale_order_id', '=', order.id)])
        self.assertEqual(account.aup_agreement_id, self.agreement)
        self.assertTrue(account.aup_accepted_on)
        self.assertEqual(account.aup_accepted_ip, '127.0.0.1')

    def test_provisioning_without_acceptance_logs_a_chatter_warning(self):
        self._mock_client()
        order = self._hosting_order()

        order.action_confirm()

        account = self.env['hestiacp.account'].search([('sale_order_id', '=', order.id)])
        self.assertFalse(account.aup_accepted_on)
        self.assertTrue(any(
            'No Hosting Service Agreement acceptance is on record' in (msg.body or '')
            for msg in account.message_ids))
