# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestHestiaCPMigrate(TransactionCase):

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
            'list_price': 10.0,
        })
        cls.no_package_name = cls.env['product.template'].create({
            'name': 'Misconfigured Hosting',
            'is_hosting_package': True,
            'hestiacp_server_id': cls.server.id,
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

    def _wizard(self, **overrides):
        vals = {
            'partner_id': self.partner.id,
            'product_id': self.product.id,
            'next_renewal_date': '2027-01-01',
        }
        vals.update(overrides)
        return self.env['hestiacp.account.migrate'].create(vals)

    def test_migrate_provisions_the_account_immediately(self):
        client = self._mock_client()

        self._wizard().action_migrate()

        add_user_calls = [c for c in client.call.call_args_list if c.args[0] == 'v-add-user']
        self.assertEqual(len(add_user_calls), 1)
        args = add_user_calls[0].args
        # (cmd, username, password, email, package, name) - password is
        # random, not asserted on
        self.assertEqual(args[3], self.partner.email)
        self.assertEqual(args[4], 'basic')
        self.assertEqual(args[5], self.partner.name)

    def test_migrate_creates_an_active_account(self):
        self._mock_client()

        self._wizard().action_migrate()

        account = self.env['hestiacp.account'].search([('partner_id', '=', self.partner.id)])
        self.assertEqual(len(account), 1)
        self.assertEqual(account.state, 'active')

    def test_migrate_uses_a_provided_username(self):
        self._mock_client()

        self._wizard(username='old-host-username').action_migrate()

        account = self.env['hestiacp.account'].search([('partner_id', '=', self.partner.id)])
        self.assertEqual(account.username, 'old-host-username')

    def test_migrate_defers_billing_to_the_given_renewal_date(self):
        self._mock_client()

        self._wizard(next_renewal_date='2027-06-15').action_migrate()

        account = self.env['hestiacp.account'].search([('partner_id', '=', self.partner.id)])
        line = account.contract_id.contract_line_ids
        self.assertEqual(line.recurring_next_date, fields.Date.from_string('2027-06-15'))

    def test_migrate_does_not_create_any_invoice(self):
        self._mock_client()

        self._wizard().action_migrate()

        account = self.env['hestiacp.account'].search([('partner_id', '=', self.partner.id)])
        invoices = account.contract_id._get_related_invoices()
        self.assertFalse(invoices)

    def test_migrate_running_the_cron_does_not_bill_before_the_renewal_date(self):
        # _recurring_create_invoice() with no date_ref falls back to
        # contract.recurring_next_date (a different field), not today -
        # the real cron (_cron_recurring_create) always passes today
        # explicitly, so that's what's simulated here.
        self._mock_client()
        self._wizard(next_renewal_date='2099-01-01').action_migrate()
        account = self.env['hestiacp.account'].search([('partner_id', '=', self.partner.id)])

        account.contract_id._recurring_create_invoice(
            date_ref=fields.Date.context_today(self))

        self.assertFalse(account.contract_id._get_related_invoices())

    def test_migrate_requires_a_package_name_on_the_product(self):
        self._mock_client()

        with self.assertRaises(UserError):
            self._wizard(product_id=self.no_package_name.id).action_migrate()

    def test_migrate_logs_a_chatter_message(self):
        self._mock_client()

        self._wizard(next_renewal_date='2027-03-01').action_migrate()

        account = self.env['hestiacp.account'].search([('partner_id', '=', self.partner.id)])
        self.assertTrue(any(
            '2027-03-01' in (msg.body or '') for msg in account.message_ids))
