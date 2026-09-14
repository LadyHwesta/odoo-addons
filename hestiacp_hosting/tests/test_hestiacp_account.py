# -*- coding: utf-8 -*-
from datetime import timedelta
from unittest.mock import MagicMock, patch

from odoo import Command, fields
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestHestiaCPAccount(TransactionCase):

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
            'name': 'Jane Customer',
            'email': 'jane@example.com',
        })

    def _mock_client(self):
        """Patch hestiacp.server._get_client to return a MagicMock instead
        of a real HestiaCPClient, so nothing here ever touches the network.
        Returns the mock so callers can assert on client.call(...).
        """
        mock_client = MagicMock()
        mock_client.call.return_value = ''
        patcher = patch(
            'odoo.addons.hestiacp_hosting.models.hestiacp_server.HestiaCPServer._get_client',
            return_value=mock_client)
        patcher.start()
        self.addCleanup(patcher.stop)
        return mock_client

    def _create_account(self):
        return self.env['hestiacp.account'].create({
            'partner_id': self.partner.id,
            'server_id': self.server.id,
            'product_id': self.product.id,
        })

    def test_provision_creates_account_and_calls_api(self):
        client = self._mock_client()
        account = self._create_account()

        account.action_provision()

        self.assertEqual(account.state, 'active')
        self.assertTrue(account.username, "provisioning should generate a username")
        called_cmds = [c.args[0] for c in client.call.call_args_list]
        self.assertIn('v-add-user', called_cmds)

    def test_provision_uses_the_products_package_name(self):
        # v-add-user's real signature (verified live 2026-09-14):
        # USER PASSWORD EMAIL PACKAGE NAME LASTNAME - package is arg4,
        # assigned in the same call rather than a separate
        # v-change-user-package call.
        client = self._mock_client()
        account = self._create_account()

        account.action_provision()

        add_user_call = next(
            c for c in client.call.call_args_list if c.args[0] == 'v-add-user')
        self.assertEqual(add_user_call.args[4], 'basic')

    def test_provision_twice_is_rejected(self):
        self._mock_client()
        account = self._create_account()
        account.action_provision()

        with self.assertRaises(Exception):
            account.action_provision()

    def test_provision_without_package_name_raises(self):
        self._mock_client()
        self.product.hestiacp_package_name = False
        account = self._create_account()

        with self.assertRaises(Exception):
            account.action_provision()

    def test_username_generation_is_unique(self):
        self._mock_client()
        account1 = self._create_account()
        account1.action_provision()

        partner2 = self.env['res.partner'].create({'name': 'Jane Customer', 'email': 'jane2@x.com'})
        account2 = self.env['hestiacp.account'].create({
            'partner_id': partner2.id,
            'server_id': self.server.id,
            'product_id': self.product.id,
        })
        account2.action_provision()

        self.assertNotEqual(account1.username, account2.username)

    def test_suspend_and_unsuspend(self):
        client = self._mock_client()
        account = self._create_account()
        account.action_provision()

        account.action_suspend()
        self.assertEqual(account.state, 'suspended')
        self.assertIn('v-suspend-user', [c.args[0] for c in client.call.call_args_list])

        account.action_unsuspend()
        self.assertEqual(account.state, 'active')
        self.assertIn('v-unsuspend-user', [c.args[0] for c in client.call.call_args_list])

    def test_suspend_only_acts_on_active_accounts(self):
        client = self._mock_client()
        account = self._create_account()
        # still in 'draft' - never provisioned
        account.action_suspend()
        self.assertEqual(account.state, 'draft')
        client.call.assert_not_called()

    def test_terminate(self):
        client = self._mock_client()
        account = self._create_account()
        account.action_provision()

        account.action_terminate()

        self.assertEqual(account.state, 'terminated')
        self.assertIn('v-delete-user', [c.args[0] for c in client.call.call_args_list])

    def _provisioned_account_with_contract(self):
        self._mock_client()
        account = self._create_account()
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
        return account, contract

    def _post_invoice_due(self, contract, due_date, paid=False):
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'invoice_date': '2026-01-01',
            'invoice_date_due': due_date,
            'invoice_line_ids': [Command.create({
                'product_id': contract.contract_line_ids[0].product_id.id,
                'quantity': 1,
                'price_unit': 10.0,
                'contract_line_id': contract.contract_line_ids[0].id,
            })],
        })
        move.action_post()
        if paid:
            self.env['account.payment.register'].with_context(
                active_model='account.move', active_ids=move.ids,
            ).create({}).action_create_payments()
        return move

    def test_cron_suspends_account_overdue_past_grace_period(self):
        account, contract = self._provisioned_account_with_contract()
        # Overdue enough to suspend, but not enough to also terminate in
        # the same run (that's covered separately below).
        overdue_10_days = fields.Date.context_today(self) - timedelta(days=10)
        self._post_invoice_due(contract, overdue_10_days)

        self.env['hestiacp.account']._cron_check_payment_status()

        self.assertEqual(account.state, 'suspended')

    def test_cron_leaves_account_active_within_grace_period(self):
        account, contract = self._provisioned_account_with_contract()
        due_soon = fields.Date.context_today(self) - timedelta(days=1)
        self._post_invoice_due(contract, due_soon)

        self.env['hestiacp.account']._cron_check_payment_status()

        self.assertEqual(account.state, 'active')

    def test_cron_unsuspends_account_once_caught_up(self):
        account, contract = self._provisioned_account_with_contract()
        account.action_suspend()
        self.assertEqual(account.state, 'suspended')
        # no unpaid invoices at all on this contract - fully caught up

        self.env['hestiacp.account']._cron_check_payment_status()

        self.assertEqual(account.state, 'active')

    def test_cron_terminates_account_suspended_past_terminate_grace_period(self):
        account, contract = self._provisioned_account_with_contract()
        account.action_suspend()
        # Backdate suspended_date to simulate having been suspended for a
        # while already - termination is gated on time spent suspended,
        # not on raw invoice-overdue days (see suspended_date's help text).
        account.suspended_date = fields.Date.context_today(self) - timedelta(days=31)
        self._post_invoice_due(contract, '2020-01-01')  # still overdue, so not caught up

        self.env['hestiacp.account']._cron_check_payment_status()

        self.assertEqual(account.state, 'terminated')

    def test_cron_does_not_terminate_a_freshly_suspended_account(self):
        # Even a very overdue invoice shouldn't jump an account straight
        # from active to terminated in a single cron run - it must sit
        # in 'suspended' for the grace period first.
        account, contract = self._provisioned_account_with_contract()
        self._post_invoice_due(contract, '2020-01-01')

        self.env['hestiacp.account']._cron_check_payment_status()

        self.assertEqual(account.state, 'suspended')
