# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestHestiaCPPortal(HttpCase):

    def _mock_client(self):
        mock_client = MagicMock()
        mock_client.call.return_value = ''
        patcher = patch(
            'odoo.addons.hestiacp_hosting.models.hestiacp_server.HestiaCPServer._get_client',
            return_value=mock_client)
        patcher.start()
        self.addCleanup(patcher.stop)
        return mock_client

    def test_my_hosting_page_shows_own_account_only(self):
        self._mock_client()
        server = self.env['hestiacp.server'].create({
            'name': 'Test Server',
            'hostname': 'https://hestia.example.com:8083',
            'access_key': 'test-access-key',
            'secret_key': 'test-secret-key',
        })
        template = self.env['product.template'].create({
            'name': 'Basic Hosting',
            'is_hosting_package': True,
            'hestiacp_server_id': server.id,
            'hestiacp_package_name': 'basic',
        })
        portal_user = self.env['res.users'].create({
            'name': 'Member Fred', 'login': 'fred_hosting', 'password': 'fred_hosting',
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        other_partner = self.env['res.partner'].create({'name': 'Someone Else'})

        own_account = self.env['hestiacp.account'].create({
            'partner_id': portal_user.partner_id.id,
            'server_id': server.id,
            'product_id': template.id,
        })
        own_account.action_provision()

        other_account = self.env['hestiacp.account'].create({
            'partner_id': other_partner.id,
            'server_id': server.id,
            'product_id': template.id,
        })
        other_account.action_provision()

        self.authenticate('fred_hosting', 'fred_hosting')

        resp = self.url_open('/my/hosting')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Basic Hosting', resp.text)
        self.assertIn(own_account.username, resp.text)
        self.assertNotIn(other_account.username, resp.text)

        home = self.url_open('/my')
        self.assertEqual(home.status_code, 200)
        self.assertIn('Hosting', home.text)

    def test_my_hosting_page_with_no_accounts(self):
        portal_user = self.env['res.users'].create({
            'name': 'Member Nobody', 'login': 'nobody_hosting', 'password': 'nobody_hosting',
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        self.authenticate('nobody_hosting', 'nobody_hosting')

        resp = self.url_open('/my/hosting')

        self.assertEqual(resp.status_code, 200)
        self.assertIn("don't have any hosting accounts", resp.text)
