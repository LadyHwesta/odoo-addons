# -*- coding: utf-8 -*-
import re
from unittest.mock import MagicMock, patch

from odoo import Command
from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestPortalSubscriptionsController(HttpCase):
    """Real HTTP round trips against /my/subscriptions and its action
    routes - especially that a portal user can only ever act on their
    own subscriptions, mirroring hestiacp_hosting's and signalwire_sms's
    own portal tests (same CSRF-token-from-a-real-page approach as
    signalwire_sms/tests/test_portal.py's own _csrf_token, rather than
    disabling CSRF protection to make testing easier).
    """

    def _mock_hestia_client(self):
        mock_client = MagicMock()
        mock_client.call.return_value = ''
        patcher = patch(
            'odoo.addons.hestiacp_hosting.models.hestiacp_server.HestiaCPServer._get_client',
            return_value=mock_client)
        patcher.start()
        self.addCleanup(patcher.stop)
        return mock_client

    def _mock_signalwire_client(self):
        patcher = patch(
            'odoo.addons.signalwire_voip.models.signalwire_server.'
            'SignalWireServer._get_client', return_value=MagicMock())
        patcher.start()
        self.addCleanup(patcher.stop)

    def _portal_user(self, login):
        return self.env['res.users'].create({
            'name': login, 'login': login, 'password': login,
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])],
        })

    def _contract(self, partner, product, price=10.0):
        return self.env['contract.contract'].create({
            'name': 'Test contract', 'partner_id': partner.id,
            'contract_type': 'sale', 'line_recurrence': True,
            'contract_line_ids': [Command.create({
                'product_id': product.id, 'name': 'Line', 'quantity': 1,
                'price_unit': price, 'date_start': '2026-01-01',
                'recurring_interval': 1, 'recurring_rule_type': 'monthly',
                'recurring_invoicing_type': 'pre-paid',
            })],
        })

    def _csrf_token(self):
        page = self.url_open('/my/subscriptions')
        match = re.search(r'name="csrf_token" value="([^"]+)"', page.text)
        self.assertTrue(match, "no csrf_token found on /my/subscriptions")
        return match.group(1)

    def setUp(self):
        super().setUp()
        self._mock_hestia_client()
        self._mock_signalwire_client()

        self.hestia_server = self.env['hestiacp.server'].create({
            'name': 'Test Server', 'hostname': 'https://h.example.com:8083',
            'access_key': 'k', 'secret_key': 's',
        })
        self.hosting_template = self.env['product.template'].create({
            'name': 'Basic Hosting', 'is_hosting_package': True,
            'hestiacp_server_id': self.hestia_server.id, 'hestiacp_package_name': 'basic',
        })
        self.pro_template = self.env['product.template'].create({
            'name': 'Pro Hosting', 'is_hosting_package': True,
            'hestiacp_server_id': self.hestia_server.id, 'hestiacp_package_name': 'pro',
        })
        self.namecheap_server = self.env['namecheap.server'].create({
            'name': 'Test Namecheap', 'api_user': 'u', 'api_key': 'k',
            'username': 'u', 'client_ip': '127.0.0.1', 'sandbox': True,
        })
        self.signalwire_server = self.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'project_id': 'pid', 'api_token': 'tok',
        })
        self.owner = self._portal_user('owner_sub')
        self.other = self._portal_user('other_sub')

        self.subproject = self.env['signalwire.subproject'].create({
            'name': 'Sub', 'server_id': self.signalwire_server.id,
            'account_sid': 'sub-abc', 'state': 'active',
            'partner_id': self.owner.partner_id.id,
        })

        self.account = self.env['hestiacp.account'].create({
            'partner_id': self.owner.partner_id.id, 'server_id': self.hestia_server.id,
            'product_id': self.hosting_template.id,
        })
        self.account.action_provision()

        self.domain = self.env['namecheap.domain'].create({
            'name': 'example.com', 'server_id': self.namecheap_server.id,
            'partner_id': self.owner.partner_id.id, 'state': 'active',
        })
        self.domain.contract_id = self._contract(
            self.owner.partner_id, self.hosting_template.product_variant_id)

        self.number = self.env['signalwire.phone_number'].create({
            'name': '+14155550100', 'sid': 'pn-123', 'subproject_id': self.subproject.id,
        })
        self.number.contract_id = self._contract(
            self.owner.partner_id, self.hosting_template.product_variant_id)

        # other_sub needs a subscription of their own too, purely so
        # /my/subscriptions renders at least one CSRF-bearing form for
        # them to grab a real token from in tests where they're the
        # one trying (and failing) to act on someone else's record.
        self.other_account = self.env['hestiacp.account'].create({
            'partner_id': self.other.partner_id.id, 'server_id': self.hestia_server.id,
            'product_id': self.hosting_template.id,
        })
        self.other_account.action_provision()

    # -- the list page ----------------------------------------------------

    def test_page_lists_every_kind_owned_by_the_user(self):
        self.authenticate('owner_sub', 'owner_sub')
        resp = self.url_open('/my/subscriptions')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Basic Hosting', resp.text)
        # exact rendered names (_subscription_summary()'s own 'name'),
        # not the bare domain/number - "example.com" alone is also a
        # substring of Odoo's own default demo-company website URL,
        # which would make a too-broad assertIn/assertNotIn here
        # meaningless regardless of actual ownership scoping.
        self.assertIn('Domain: example.com', resp.text)
        self.assertIn('Phone Number: +14155550100', resp.text)

    def test_page_does_not_show_another_users_subscriptions(self):
        self.authenticate('other_sub', 'other_sub')
        resp = self.url_open('/my/subscriptions')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('Domain: example.com', resp.text)
        self.assertNotIn('Phone Number: +14155550100', resp.text)

    # -- ownership checks on every action route ----------------------------

    def test_other_user_cannot_cancel_the_hosting_account(self):
        self.authenticate('other_sub', 'other_sub')
        csrf_token = self._csrf_token()
        self.url_open(
            f'/my/subscriptions/hosting/{self.account.id}/cancel',
            data={'csrf_token': csrf_token})
        self.assertEqual(self.account.state, 'active', "must not have been terminated")

    def test_other_user_cannot_cancel_the_domain(self):
        self.authenticate('other_sub', 'other_sub')
        csrf_token = self._csrf_token()
        self.url_open(
            f'/my/subscriptions/domain/{self.domain.id}/cancel_renewal',
            data={'csrf_token': csrf_token})
        self.assertEqual(self.domain.state, 'active')

    def test_other_user_cannot_release_the_number(self):
        self.authenticate('other_sub', 'other_sub')
        csrf_token = self._csrf_token()
        self.url_open(
            f'/my/subscriptions/signalwire/{self.number.id}/release',
            data={'csrf_token': csrf_token})
        self.assertTrue(self.number.active)

    def test_other_user_cannot_change_the_hosting_package(self):
        self.authenticate('other_sub', 'other_sub')
        csrf_token = self._csrf_token()
        self.url_open(
            f'/my/subscriptions/hosting/{self.account.id}/upgrade',
            data={'csrf_token': csrf_token, 'new_product_id': self.pro_template.id})
        self.assertEqual(self.account.product_id, self.hosting_template)

    def test_other_user_cannot_assign_their_card_to_someone_elses_subscription(self):
        provider = self.env['payment.provider'].create({
            'name': 'Test Provider', 'code': 'none', 'state': 'test',
        })
        method = self.env['payment.method'].create({'name': 'Card', 'code': 'test_card'})
        other_token = self.env['payment.token'].create({
            'provider_id': provider.id, 'payment_method_id': method.id,
            'partner_id': self.other.partner_id.id, 'provider_ref': 'ref-2',
            'payment_details': '5678',
        })
        self.authenticate('other_sub', 'other_sub')
        csrf_token = self._csrf_token()
        self.url_open(
            f'/my/subscriptions/hosting/{self.account.id}/payment_method',
            data={'csrf_token': csrf_token, 'token_id': other_token.id})
        self.assertFalse(self.account.payment_token_id)

    # -- the owner's own actions actually work ------------------------------

    def test_owner_can_cancel_the_hosting_account(self):
        self.authenticate('owner_sub', 'owner_sub')
        csrf_token = self._csrf_token()
        self.url_open(
            f'/my/subscriptions/hosting/{self.account.id}/cancel',
            data={'csrf_token': csrf_token})
        self.assertEqual(self.account.state, 'terminated')

    def test_owner_can_cancel_renewal_on_their_domain(self):
        self.authenticate('owner_sub', 'owner_sub')
        csrf_token = self._csrf_token()
        self.url_open(
            f'/my/subscriptions/domain/{self.domain.id}/cancel_renewal',
            data={'csrf_token': csrf_token})
        self.assertEqual(self.domain.state, 'cancelled')

    def test_owner_can_release_their_number(self):
        self.authenticate('owner_sub', 'owner_sub')
        csrf_token = self._csrf_token()
        self.url_open(
            f'/my/subscriptions/signalwire/{self.number.id}/release',
            data={'csrf_token': csrf_token})
        self.assertFalse(self.number.active)

    def test_owner_can_change_hosting_package(self):
        self.authenticate('owner_sub', 'owner_sub')
        csrf_token = self._csrf_token()
        self.url_open(
            f'/my/subscriptions/hosting/{self.account.id}/upgrade',
            data={'csrf_token': csrf_token, 'new_product_id': self.pro_template.id})
        self.assertEqual(self.account.product_id, self.pro_template)

    def test_owner_can_assign_their_own_saved_card(self):
        provider = self.env['payment.provider'].create({
            'name': 'Test Provider', 'code': 'none', 'state': 'test',
        })
        method = self.env['payment.method'].create({'name': 'Card', 'code': 'test_card'})
        token = self.env['payment.token'].create({
            'provider_id': provider.id, 'payment_method_id': method.id,
            'partner_id': self.owner.partner_id.id, 'provider_ref': 'ref-1',
            'payment_details': '1234',
        })
        self.authenticate('owner_sub', 'owner_sub')
        csrf_token = self._csrf_token()
        self.url_open(
            f'/my/subscriptions/hosting/{self.account.id}/payment_method',
            data={'csrf_token': csrf_token, 'token_id': token.id})
        self.assertEqual(self.account.payment_token_id, token)
