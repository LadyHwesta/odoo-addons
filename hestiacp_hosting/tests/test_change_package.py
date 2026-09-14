# -*- coding: utf-8 -*-
from datetime import timedelta
from unittest.mock import MagicMock, patch

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.hestiacp_hosting.models.hestiacp_api import HestiaCPAPIError


@tagged('post_install', '-at_install')
class TestHestiaCPChangePackage(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['hestiacp.server'].create({
            'name': 'Test Server',
            'hostname': 'https://hestia.example.com:8083',
            'access_key': 'test-access-key',
            'secret_key': 'test-secret-key',
        })
        cls.other_server = cls.env['hestiacp.server'].create({
            'name': 'Other Server',
            'hostname': 'https://other.example.com:8083',
            'access_key': 'test-access-key-2',
            'secret_key': 'test-secret-key-2',
        })
        cls.basic = cls.env['product.template'].create({
            'name': 'Basic Hosting',
            'is_hosting_package': True,
            'hestiacp_server_id': cls.server.id,
            'hestiacp_package_name': 'basic',
            'list_price': 10.0,
        })
        cls.pro = cls.env['product.template'].create({
            'name': 'Pro Hosting',
            'is_hosting_package': True,
            'hestiacp_server_id': cls.server.id,
            'hestiacp_package_name': 'pro',
            'list_price': 25.0,
        })
        cls.no_package_name = cls.env['product.template'].create({
            'name': 'Misconfigured Hosting',
            'is_hosting_package': True,
            'hestiacp_server_id': cls.server.id,
            'list_price': 15.0,
        })
        cls.other_server_product = cls.env['product.template'].create({
            'name': 'Other Server Hosting',
            'is_hosting_package': True,
            'hestiacp_server_id': cls.other_server.id,
            'hestiacp_package_name': 'basic',
            'list_price': 10.0,
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

    def _provisioned_account(self, product=None, with_contract=True):
        # Callers are expected to have already called self._mock_client()
        # themselves - not done here, so that a single mock instance stays
        # active (and assertable) across both provisioning and whatever
        # the test does with the account afterward.
        product = product or self.basic
        account = self.env['hestiacp.account'].create({
            'partner_id': self.partner.id,
            'server_id': self.server.id,
            'product_id': product.id,
        })
        if with_contract:
            contract = self.env['contract.contract'].create({
                'name': 'Test contract',
                'partner_id': self.partner.id,
                'contract_type': 'sale',
                'line_recurrence': True,
                'contract_line_ids': [Command.create({
                    'product_id': self.env['product.product'].search(
                        [('product_tmpl_id', '=', product.id)], limit=1).id,
                    'name': product.name,
                    'quantity': 1,
                    'price_unit': product.list_price,
                    'date_start': '2026-01-01',
                    'recurring_interval': 1,
                    'recurring_rule_type': 'monthly',
                    'recurring_invoicing_type': 'pre-paid',
                })],
            })
            account.contract_id = contract
        account.action_provision()
        return account

    def _wizard(self, account, new_product):
        return self.env['hestiacp.account.change.package'].create({
            'account_id': account.id,
            'new_product_id': new_product.id,
        })

    def _invoice_current_line(self, account):
        """Run the contract's own recurring-invoice creation once, the
        same as its renewal cron would - needed to move the line past
        the "nothing invoiced yet" case (where _change_billing_line
        updates the line in place) into the normal "already paid for
        the current period" case (where it ends the old line and starts
        a new one at the next renewal). Only this - not a hand-built
        account.move - actually advances last_date_invoiced.
        """
        return account.contract_id._recurring_create_invoice()

    # -- happy path ----------------------------------------------------

    def test_change_package_calls_hestiacp_and_updates_the_account(self):
        client = self._mock_client()
        account = self._provisioned_account()

        self._wizard(account, self.pro).action_confirm()

        client.call.assert_any_call('v-change-user-package', account.username, 'pro')
        self.assertEqual(account.product_id, self.pro)

    def test_change_package_does_not_pass_force(self):
        client = self._mock_client()
        account = self._provisioned_account()

        self._wizard(account, self.pro).action_confirm()

        # exactly USER and PACKAGE - no third (force) argument, so
        # HestiaCP's own usage-vs-limits check always runs
        call_args = [c for c in client.call.call_args_list
                     if c.args and c.args[0] == 'v-change-user-package'][0]
        self.assertEqual(call_args.args, ('v-change-user-package', account.username, 'pro'))

    def test_change_package_logs_a_chatter_message(self):
        self._mock_client()
        account = self._provisioned_account()

        self._wizard(account, self.pro).action_confirm()

        self.assertTrue(any(
            'Basic Hosting' in (msg.body or '') and 'Pro Hosting' in (msg.body or '')
            for msg in account.message_ids))

    # -- HestiaCP's own downgrade safety check --------------------------

    def test_hestiacp_refusal_surfaces_as_a_clear_error(self):
        client = self._mock_client()
        account = self._provisioned_account(product=self.pro)

        def side_effect(cmd, *args):
            if cmd == 'v-change-user-package':
                raise HestiaCPAPIError(
                    "HestiaCP command v-change-user-package failed (exit 4): "
                    "Error: Package doesn't cover MAIL_DOMAIN usage")
            return ''
        client.call.side_effect = side_effect

        with self.assertRaises(HestiaCPAPIError) as cm:
            self._wizard(account, self.basic).action_confirm()
        self.assertIn('MAIL_DOMAIN', str(cm.exception))
        # nothing on the Odoo side should have changed if HestiaCP refused
        self.assertEqual(account.product_id, self.pro)

    # -- billing transition ---------------------------------------------

    def test_change_package_before_any_invoice_updates_the_line_in_place(self):
        """A same-day change on a brand new account, before its first
        invoice has ever gone out: there's no already-paid period to
        preserve, so the existing line is just repointed at the new
        product - its very next (first-ever) invoice is already at the
        new price, rather than deferred to a later renewal.
        """
        self._mock_client()
        account = self._provisioned_account()
        old_line = account.contract_id.contract_line_ids
        self.assertFalse(old_line.last_date_invoiced)

        self._wizard(account, self.pro).action_confirm()

        self.assertEqual(account.contract_id.contract_line_ids, old_line)
        self.assertEqual(old_line.product_id.product_tmpl_id, self.pro)
        self.assertEqual(old_line.price_unit, 25.0)
        self.assertFalse(old_line.date_end)

    def test_change_package_after_an_invoice_defers_to_the_next_renewal(self):
        """Once at least one invoice has gone out, the change instead
        ends the current line at its next renewal date and starts a new
        one there - the already-invoiced period is left untouched.
        """
        self._mock_client()
        account = self._provisioned_account()
        old_line = account.contract_id.contract_line_ids
        self._invoice_current_line(account)
        self.assertTrue(old_line.last_date_invoiced)
        next_date = old_line.recurring_next_date

        self._wizard(account, self.pro).action_confirm()

        new_line = account.contract_id.contract_line_ids - old_line
        self.assertEqual(len(new_line), 1)
        self.assertEqual(new_line.product_id.product_tmpl_id, self.pro)
        self.assertEqual(new_line.price_unit, 25.0)
        self.assertEqual(new_line.date_start, next_date)
        self.assertEqual(old_line.date_end, next_date - timedelta(days=1))
        self.assertEqual(old_line.product_id.product_tmpl_id, self.basic,
                          "the already-invoiced old line should keep its original product")

    def test_change_package_without_a_contract_does_not_raise(self):
        self._mock_client()
        account = self._provisioned_account(with_contract=False)

        # should not raise even though there's no contract to update
        self._wizard(account, self.pro).action_confirm()
        self.assertEqual(account.product_id, self.pro)

    # -- guardrails -------------------------------------------------------

    def test_cannot_change_package_on_a_non_active_account(self):
        self._mock_client()
        account = self._provisioned_account()
        account.action_suspend()

        with self.assertRaises(UserError):
            self._wizard(account, self.pro).action_confirm()

    def test_cannot_change_to_the_same_package(self):
        self._mock_client()
        account = self._provisioned_account(product=self.pro)

        with self.assertRaises(UserError):
            self._wizard(account, self.pro).action_confirm()

    def test_cannot_change_to_a_product_without_a_package_name(self):
        self._mock_client()
        account = self._provisioned_account()

        with self.assertRaises(UserError):
            self._wizard(account, self.no_package_name).action_confirm()

    def test_cannot_change_to_a_product_on_a_different_server(self):
        self._mock_client()
        account = self._provisioned_account()

        with self.assertRaises(UserError):
            self._wizard(account, self.other_server_product).action_confirm()
