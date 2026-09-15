# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo import Command
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSubscriptionSummary(TransactionCase):
    """_subscription_summary()'s uniform shape is what lets one portal
    template render hosting/domains/SignalWire generically - covers
    all three implementations, with and without a contract/payment
    token, and that can_upgrade/can_cancel reflect each model's own
    real state semantics.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Jane Customer'})
        cls.provider = cls.env['payment.provider'].create({
            'name': 'Test Provider', 'code': 'none', 'state': 'test',
        })
        cls.payment_method = cls.env['payment.method'].create({
            'name': 'Test Card', 'code': 'test_card',
        })
        cls.token = cls.env['payment.token'].create({
            'provider_id': cls.provider.id, 'payment_method_id': cls.payment_method.id,
            'partner_id': cls.partner.id, 'provider_ref': 'ref-1', 'payment_details': '1234',
        })

    def _contract(self, product, price=10.0):
        return self.env['contract.contract'].create({
            'name': 'Test contract', 'partner_id': self.partner.id,
            'contract_type': 'sale', 'line_recurrence': True,
            'contract_line_ids': [Command.create({
                'product_id': product.id, 'name': 'Line', 'quantity': 1,
                'price_unit': price, 'date_start': '2026-01-01',
                'recurring_interval': 1, 'recurring_rule_type': 'monthly',
                'recurring_invoicing_type': 'pre-paid',
            })],
        })

    # -- hosting -------------------------------------------------------

    def _mock_hestia_client(self):
        mock_client = MagicMock()
        mock_client.call.return_value = ''
        patcher = patch(
            'odoo.addons.hestiacp_hosting.models.hestiacp_server.HestiaCPServer._get_client',
            return_value=mock_client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_hosting_summary_active_with_contract_and_token(self):
        self._mock_hestia_client()
        server = self.env['hestiacp.server'].create({
            'name': 'Test Server', 'hostname': 'https://h.example.com:8083',
            'access_key': 'k', 'secret_key': 's',
        })
        template = self.env['product.template'].create({
            'name': 'Basic Hosting', 'is_hosting_package': True,
            'hestiacp_server_id': server.id, 'hestiacp_package_name': 'basic',
            'list_price': 10.0,
        })
        account = self.env['hestiacp.account'].create({
            'partner_id': self.partner.id, 'server_id': server.id,
            'product_id': template.id, 'payment_token_id': self.token.id,
        })
        account.contract_id = self._contract(template.product_variant_id)
        account.action_provision()

        summary = account._subscription_summary()

        self.assertIn('Basic Hosting', summary['name'])
        self.assertEqual(summary['state'], 'active')
        self.assertTrue(summary['can_upgrade'])
        self.assertTrue(summary['can_cancel'])
        self.assertTrue(summary['has_payment_method'])
        self.assertEqual(summary['monthly_amount'], 10.0)
        self.assertEqual(summary['portal_view_url'], '/my/hosting')

    def test_hosting_summary_without_contract_or_token(self):
        self._mock_hestia_client()
        server = self.env['hestiacp.server'].create({
            'name': 'Test Server', 'hostname': 'https://h.example.com:8083',
            'access_key': 'k', 'secret_key': 's',
        })
        template = self.env['product.template'].create({
            'name': 'Basic Hosting', 'is_hosting_package': True,
            'hestiacp_server_id': server.id, 'hestiacp_package_name': 'basic',
        })
        account = self.env['hestiacp.account'].create({
            'partner_id': self.partner.id, 'server_id': server.id, 'product_id': template.id,
        })

        summary = account._subscription_summary()

        self.assertFalse(summary['has_payment_method'])
        self.assertFalse(summary['next_invoice_date'])
        self.assertEqual(summary['monthly_amount'], 0.0)
        # not yet provisioned (state='draft') - can't upgrade/cancel yet
        self.assertFalse(summary['can_upgrade'])
        self.assertFalse(summary['can_cancel'])

    # -- domains ---------------------------------------------------------

    def test_domain_summary_active(self):
        server = self.env['namecheap.server'].create({
            'name': 'Test Namecheap', 'api_user': 'u', 'api_key': 'k',
            'username': 'u', 'client_ip': '127.0.0.1', 'sandbox': True,
        })
        template = self.env['product.template'].create({
            'name': 'Domain Registration', 'is_domain_registration': True,
        })
        domain = self.env['namecheap.domain'].create({
            'name': 'example.com', 'server_id': server.id,
            'partner_id': self.partner.id, 'state': 'active',
            'payment_token_id': self.token.id,
        })
        domain.contract_id = self._contract(template.product_variant_id, price=12.0)

        summary = domain._subscription_summary()

        self.assertIn('example.com', summary['name'])
        self.assertFalse(summary['can_upgrade'], "domains have no tier concept")
        self.assertTrue(summary['can_cancel'])
        self.assertEqual(summary['monthly_amount'], 12.0)
        self.assertTrue(summary['portal_view_url'].startswith('/my/contracts/'))

    def test_domain_summary_cancelled_cannot_be_cancelled_again(self):
        server = self.env['namecheap.server'].create({
            'name': 'Test Namecheap', 'api_user': 'u', 'api_key': 'k',
            'username': 'u', 'client_ip': '127.0.0.1', 'sandbox': True,
        })
        domain = self.env['namecheap.domain'].create({
            'name': 'example.com', 'server_id': server.id,
            'partner_id': self.partner.id, 'state': 'cancelled',
        })

        summary = domain._subscription_summary()
        self.assertFalse(summary['can_cancel'])

    # -- signalwire numbers ------------------------------------------------

    def test_signalwire_summary_active(self):
        signalwire_server = self.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'project_id': 'pid', 'api_token': 'tok',
        })
        subproject = self.env['signalwire.subproject'].create({
            'name': 'Sub', 'server_id': signalwire_server.id,
            'account_sid': 'sub-abc', 'state': 'active', 'partner_id': self.partner.id,
        })
        template = self.env['product.template'].create({
            'name': 'VoIP Number', 'is_voip_number': True,
        })
        number = self.env['signalwire.phone_number'].create({
            'name': '+14155550100', 'sid': 'pn-123', 'subproject_id': subproject.id,
            'payment_token_id': self.token.id,
        })
        number.contract_id = self._contract(template.product_variant_id, price=5.0)

        summary = number._subscription_summary()

        self.assertIn('+14155550100', summary['name'])
        self.assertEqual(summary['state'], 'active')
        self.assertFalse(summary['can_upgrade'])
        self.assertTrue(summary['can_cancel'])
        self.assertEqual(summary['monthly_amount'], 5.0)

    def test_signalwire_summary_released(self):
        signalwire_server = self.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'project_id': 'pid', 'api_token': 'tok',
        })
        subproject = self.env['signalwire.subproject'].create({
            'name': 'Sub', 'server_id': signalwire_server.id,
            'account_sid': 'sub-abc', 'state': 'active', 'partner_id': self.partner.id,
        })
        number = self.env['signalwire.phone_number'].create({
            'name': '+14155550100', 'sid': 'pn-123', 'subproject_id': subproject.id,
        })
        with patch(
                'odoo.addons.signalwire_voip.models.signalwire_server.'
                'SignalWireServer._get_client', return_value=MagicMock()):
            number.action_release()

        summary = number._subscription_summary()
        self.assertEqual(summary['state'], 'released')
        self.assertFalse(summary['can_cancel'])
