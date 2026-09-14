# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo import Command
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestHestiaCPAutoCharge(TransactionCase):
    """Covers _charge_invoice/_cron_auto_charge_due_invoices - the
    orchestration around Odoo's own payment.transaction._charge_with_token
    (core, not re-tested here). _send_payment_request is the method a
    real provider module overrides to actually talk to the gateway; the
    base implementation is a no-op, so it's mocked here to simulate a
    provider's outcome without needing real Stripe credentials.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['hestiacp.server'].create({
            'name': 'Test Server',
            'hostname': 'https://hestia.example.com:8083',
            'access_key': 'test-access-key',
            'secret_key': 'test-secret-key',
        })
        cls.product = cls.env['product.template'].create({
            'name': 'Basic Hosting',
            'is_hosting_package': True,
            'hestiacp_server_id': cls.server.id,
            'hestiacp_package_name': 'basic',
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'Jane Customer', 'email': 'jane@example.com',
        })
        cls.provider = cls.env['payment.provider'].create({
            'name': 'Test Provider', 'code': 'none', 'state': 'test',
        })
        cls.payment_method = cls.env['payment.method'].create({
            'name': 'Test Card', 'code': 'test_card',
        })
        cls.token = cls.env['payment.token'].create({
            'provider_id': cls.provider.id,
            'payment_method_id': cls.payment_method.id,
            'partner_id': cls.partner.id,
            'provider_ref': 'test-ref-1',
            'payment_details': '1234',
        })

    def _mock_hestia_client(self):
        mock_client = MagicMock()
        mock_client.call.return_value = ''
        patcher = patch(
            'odoo.addons.hestiacp_hosting.models.hestiacp_server.HestiaCPServer._get_client',
            return_value=mock_client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _provisioned_account_with_invoice(self, with_token=True):
        self._mock_hestia_client()
        account = self.env['hestiacp.account'].create({
            'partner_id': self.partner.id,
            'server_id': self.server.id,
            'product_id': self.product.id,
            'payment_token_id': self.token.id if with_token else False,
        })
        contract = self.env['contract.contract'].create({
            'name': 'Test contract',
            'partner_id': self.partner.id,
            'contract_type': 'sale',
            'line_recurrence': True,
            'contract_line_ids': [Command.create({
                'product_id': self.env['product.product'].search(
                    [('product_tmpl_id', '=', self.product.id)], limit=1).id,
                'name': 'Basic Hosting',
                'quantity': 1,
                'price_unit': 10.0,
                'date_start': '2026-01-01',
                'recurring_interval': 1,
                'recurring_rule_type': 'monthly',
                'recurring_invoicing_type': 'pre-paid',
            })],
        })
        account.contract_id = contract
        account.action_provision()

        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'invoice_date': '2026-01-01',
            'invoice_line_ids': [Command.create({
                'product_id': contract.contract_line_ids[0].product_id.id,
                'quantity': 1,
                'price_unit': 10.0,
                'contract_line_id': contract.contract_line_ids[0].id,
            })],
        })
        invoice.action_post()
        return account, invoice

    def test_charge_invoice_creates_a_correctly_shaped_transaction(self):
        account, invoice = self._provisioned_account_with_invoice()

        with patch('odoo.addons.payment.models.payment_transaction.'
                   'PaymentTransaction._send_payment_request'):
            tx = account._charge_invoice(invoice)

        self.assertEqual(tx.token_id, self.token)
        self.assertEqual(tx.partner_id, self.partner)
        self.assertEqual(tx.amount, invoice.amount_residual)
        self.assertEqual(tx.invoice_ids, invoice)
        self.assertEqual(tx.operation, 'offline')

    def test_cron_charges_due_invoice_when_token_present(self):
        account, invoice = self._provisioned_account_with_invoice(with_token=True)

        with patch('odoo.addons.payment.models.payment_transaction.'
                   'PaymentTransaction._send_payment_request'):
            self.env['hestiacp.account']._cron_auto_charge_due_invoices()

        self.assertTrue(invoice.transaction_ids, "a charge attempt should have been made")

    def test_cron_skips_accounts_without_a_payment_token(self):
        account, invoice = self._provisioned_account_with_invoice(with_token=False)

        with patch('odoo.addons.payment.models.payment_transaction.'
                   'PaymentTransaction._send_payment_request') as mock_send:
            self.env['hestiacp.account']._cron_auto_charge_due_invoices()

        mock_send.assert_not_called()
        self.assertFalse(invoice.transaction_ids)

    def test_cron_does_not_double_charge_an_already_attempted_invoice(self):
        account, invoice = self._provisioned_account_with_invoice(with_token=True)
        with patch('odoo.addons.payment.models.payment_transaction.'
                   'PaymentTransaction._send_payment_request'):
            account._charge_invoice(invoice)
        self.assertEqual(len(invoice.transaction_ids), 1)

        with patch('odoo.addons.payment.models.payment_transaction.'
                   'PaymentTransaction._send_payment_request') as mock_send:
            self.env['hestiacp.account']._cron_auto_charge_due_invoices()

        mock_send.assert_not_called()
        self.assertEqual(len(invoice.transaction_ids), 1)

    def test_cron_skips_invoices_already_fully_paid(self):
        account, invoice = self._provisioned_account_with_invoice(with_token=True)
        invoice.payment_state = 'paid'  # simulate already settled another way

        with patch('odoo.addons.payment.models.payment_transaction.'
                   'PaymentTransaction._send_payment_request') as mock_send:
            self.env['hestiacp.account']._cron_auto_charge_due_invoices()

        mock_send.assert_not_called()

    def test_cron_skips_non_active_accounts(self):
        account, invoice = self._provisioned_account_with_invoice(with_token=True)
        account.action_suspend()

        with patch('odoo.addons.payment.models.payment_transaction.'
                   'PaymentTransaction._send_payment_request') as mock_send:
            self.env['hestiacp.account']._cron_auto_charge_due_invoices()

        mock_send.assert_not_called()

    def test_charge_failure_does_not_stop_the_cron_for_other_accounts(self):
        account1, invoice1 = self._provisioned_account_with_invoice(with_token=True)
        partner2 = self.env['res.partner'].create({'name': 'Second Customer'})
        token2 = self.env['payment.token'].create({
            'provider_id': self.provider.id,
            'payment_method_id': self.payment_method.id,
            'partner_id': partner2.id,
            'provider_ref': 'test-ref-2',
            'payment_details': '5678',
        })
        self._mock_hestia_client()
        account2 = self.env['hestiacp.account'].create({
            'partner_id': partner2.id,
            'server_id': self.server.id,
            'product_id': self.product.id,
            'payment_token_id': token2.id,
        })
        contract2 = self.env['contract.contract'].create({
            'name': 'Test contract 2',
            'partner_id': partner2.id,
            'contract_type': 'sale',
            'line_recurrence': True,
            'contract_line_ids': [Command.create({
                'product_id': self.env['product.product'].search(
                    [('product_tmpl_id', '=', self.product.id)], limit=1).id,
                'name': 'Basic Hosting',
                'quantity': 1,
                'price_unit': 10.0,
                'date_start': '2026-01-01',
                'recurring_interval': 1,
                'recurring_rule_type': 'monthly',
                'recurring_invoicing_type': 'pre-paid',
            })],
        })
        account2.contract_id = contract2
        account2.action_provision()
        invoice2 = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner2.id,
            'invoice_date': '2026-01-01',
            'invoice_line_ids': [Command.create({
                'product_id': contract2.contract_line_ids[0].product_id.id,
                'quantity': 1,
                'price_unit': 10.0,
                'contract_line_id': contract2.contract_line_ids[0].id,
            })],
        })
        invoice2.action_post()

        def side_effect(self_tx):
            if self_tx.invoice_ids == invoice1:
                raise Exception("simulated gateway failure for account1")

        with patch('odoo.addons.payment.models.payment_transaction.'
                   'PaymentTransaction._send_payment_request', side_effect=side_effect,
                   autospec=True):
            # Should not raise, and should still process account2.
            self.env['hestiacp.account']._cron_auto_charge_due_invoices()

        self.assertTrue(invoice2.transaction_ids,
                         "account2 should still be charged despite account1's failure")
