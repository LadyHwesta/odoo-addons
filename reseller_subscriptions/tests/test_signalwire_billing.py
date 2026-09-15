# -*- coding: utf-8 -*-
from datetime import date
from unittest.mock import MagicMock, patch

from odoo import Command
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSignalWireBilling(TransactionCase):
    """Covers the actual gap this module closes: signalwire.phone_number
    gaining contract_id/payment_token_id, _signalwire_after_provisioned
    storing them, action_release ending the contract line, and the
    auto-charge cron - same orchestration hestiacp_hosting's own
    test_auto_charge.py already covers for hestiacp.account, mirrored
    here for the new consumer.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'project_id': 'pid123', 'api_token': 'tok456',
        })
        cls.partner = cls.env['res.partner'].create({'name': 'Jane Customer'})
        cls.subproject = cls.env['signalwire.subproject'].create({
            'name': 'Test Subproject', 'server_id': cls.server.id,
            'account_sid': 'sub-abc', 'state': 'active', 'partner_id': cls.partner.id,
        })
        rental_template = cls.env['product.template'].create({
            'name': 'VoIP Number', 'is_voip_number': True,
        })
        cls.rental_product = rental_template.product_variant_id
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

    def setUp(self):
        super().setUp()
        self.signalwire_client = MagicMock()
        patcher = patch(
            'odoo.addons.signalwire_voip.models.signalwire_server.'
            'SignalWireServer._get_client', return_value=self.signalwire_client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _number_with_contract(self, with_token=True):
        number = self.env['signalwire.phone_number'].create({
            'name': '+14155550100', 'sid': 'pn-123', 'subproject_id': self.subproject.id,
        })
        contract = self.env['contract.contract'].create({
            'name': 'Test VoIP contract', 'partner_id': self.partner.id,
            'contract_type': 'sale', 'line_recurrence': True,
            'contract_line_ids': [Command.create({
                'product_id': self.rental_product.id,
                'name': 'Monthly rental', 'quantity': 1, 'price_unit': 5.0,
                'date_start': '2026-01-01', 'recurring_interval': 1,
                'recurring_rule_type': 'monthly', 'recurring_invoicing_type': 'pre-paid',
            })],
        })
        number.write({
            'contract_id': contract.id,
            'payment_token_id': self.token.id if with_token else False,
        })
        return number, contract

    # -- _signalwire_after_provisioned -------------------------------------

    def test_after_provisioned_stores_contract_and_token(self):
        number = self.env['signalwire.phone_number'].create({
            'name': '+14155550100', 'sid': 'pn-123', 'subproject_id': self.subproject.id,
        })
        contract = self.env['contract.contract'].create({
            'name': 'Test contract', 'partner_id': self.partner.id,
            'contract_type': 'sale', 'line_recurrence': True,
        })
        checkout_tx = MagicMock(token_id=self.token)

        number._signalwire_after_provisioned(contract, checkout_tx)

        self.assertEqual(number.contract_id, contract)
        self.assertEqual(number.payment_token_id, self.token)

    def test_after_provisioned_without_a_checkout_transaction(self):
        number = self.env['signalwire.phone_number'].create({
            'name': '+14155550100', 'sid': 'pn-123', 'subproject_id': self.subproject.id,
        })
        contract = self.env['contract.contract'].create({
            'name': 'Test contract', 'partner_id': self.partner.id,
            'contract_type': 'sale', 'line_recurrence': True,
        })

        number._signalwire_after_provisioned(contract, False)

        self.assertEqual(number.contract_id, contract)
        self.assertFalse(number.payment_token_id)

    # -- action_release now stops billing ----------------------------------

    def test_release_ends_the_open_contract_line(self):
        number, contract = self._number_with_contract()
        line = contract.contract_line_ids
        self.assertFalse(line.date_end)

        number.action_release()

        self.assertEqual(line.date_end, date.today())

    def test_release_without_a_contract_does_not_raise(self):
        number = self.env['signalwire.phone_number'].create({
            'name': '+14155550100', 'sid': 'pn-123', 'subproject_id': self.subproject.id,
        })
        number.action_release()  # should not raise
        self.assertFalse(number.active)

    def test_release_still_calls_signalwire(self):
        number, _contract = self._number_with_contract()
        number.action_release()
        self.signalwire_client.compat_delete.assert_called_once_with(
            'Accounts/sub-abc/IncomingPhoneNumbers/pn-123.json')

    # -- auto-charge cron ---------------------------------------------------

    def _due_invoice(self, contract):
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': self.partner.id,
            'invoice_date': '2026-01-01',
            'invoice_line_ids': [Command.create({
                'product_id': contract.contract_line_ids[0].product_id.id,
                'quantity': 1, 'price_unit': 5.0,
                'contract_line_id': contract.contract_line_ids[0].id,
            })],
        })
        invoice.action_post()
        return invoice

    def test_cron_charges_due_invoice_when_token_present(self):
        number, contract = self._number_with_contract(with_token=True)
        invoice = self._due_invoice(contract)

        with patch('odoo.addons.payment.models.payment_transaction.'
                   'PaymentTransaction._send_payment_request'):
            self.env['signalwire.phone_number']._cron_signalwire_auto_charge()

        self.assertTrue(invoice.transaction_ids)

    def test_cron_skips_numbers_without_a_token(self):
        number, contract = self._number_with_contract(with_token=False)
        invoice = self._due_invoice(contract)

        with patch('odoo.addons.payment.models.payment_transaction.'
                   'PaymentTransaction._send_payment_request') as mock_send:
            self.env['signalwire.phone_number']._cron_signalwire_auto_charge()

        mock_send.assert_not_called()
        self.assertFalse(invoice.transaction_ids)

    def test_cron_skips_released_numbers(self):
        number, contract = self._number_with_contract(with_token=True)
        invoice = self._due_invoice(contract)
        number.action_release()

        with patch('odoo.addons.payment.models.payment_transaction.'
                   'PaymentTransaction._send_payment_request') as mock_send:
            self.env['signalwire.phone_number']._cron_signalwire_auto_charge()

        mock_send.assert_not_called()
