# -*- coding: utf-8 -*-
import json
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


def _user_info(username, web_limit='5', web_used='1', ns='ns1.example.com,ns2.example.com'):
    return json.dumps({username: {
        'WEB_DOMAINS': web_limit,
        'U_WEB_DOMAINS': web_used,
        'NS': ns,
    }})


def _dns_records(include_dkim=True):
    records = {
        '1': {'RECORD': 'example.com.', 'TYPE': 'A', 'VALUE': '1.2.3.4'},
        '2': {'RECORD': 'example.com.', 'TYPE': 'MX', 'VALUE': 'mail.example.com.'},
    }
    if include_dkim:
        records['3'] = {
            'RECORD': 'mail._domainkey.example.com.', 'TYPE': 'TXT',
            'VALUE': 'v=DKIM1; k=rsa; p=ABC123FAKEKEYDATA',
        }
    return json.dumps(records)


@tagged('post_install', '-at_install')
class TestDeployToHestiaCP(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.hestia_server = cls.env['hestiacp.server'].create({
            'name': 'Test HestiaCP',
            'hostname': 'https://hestia.example.com:8083',
            'access_key': 'k', 'secret_key': 's',
        })
        cls.product = cls.env['product.template'].create({
            'name': 'Basic Hosting', 'is_hosting_package': True,
            'hestiacp_server_id': cls.hestia_server.id,
            'hestiacp_package_name': 'basic',
        })
        cls.partner = cls.env['res.partner'].create({'name': 'Jane Customer'})
        cls.namecheap_server = cls.env['namecheap.server'].create({
            'name': 'Test Namecheap', 'api_user': 'u', 'api_key': 'k',
            'username': 'u', 'client_ip': '1.2.3.4', 'sandbox': True,
        })
        cls.domain = cls.env['namecheap.domain'].create({
            'name': 'example.com', 'server_id': cls.namecheap_server.id,
            'partner_id': cls.partner.id,
        })

    def setUp(self):
        super().setUp()
        # Every action_deploy_to_hestiacp() call reaches out to BOTH
        # clients (HestiaCP for v-list-user/v-add-domain, Namecheap for
        # setting nameservers) - mocked here for every test rather than
        # per-test, so nothing accidentally makes a real HTTP call just
        # because one test forgot to mock the one it happened not to
        # assert on.
        self.namecheap_client = MagicMock()
        patcher = patch(
            'odoo.addons.namecheap_domains.models.namecheap_server.'
            'NamecheapServer._get_client',
            return_value=self.namecheap_client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _mock_hestia_client(self, user_info_json=None, dns_records_json=None):
        mock_client = MagicMock()

        def side_effect(cmd, *a):
            if cmd == 'v-list-user':
                return user_info_json
            if cmd == 'v-list-dns-records':
                return dns_records_json
            return ''
        mock_client.call.side_effect = side_effect
        patcher = patch(
            'odoo.addons.hestiacp_hosting.models.hestiacp_server.HestiaCPServer._get_client',
            return_value=mock_client)
        patcher.start()
        self.addCleanup(patcher.stop)
        return mock_client

    def _provisioned_account(self):
        account = self.env['hestiacp.account'].create({
            'partner_id': self.partner.id, 'server_id': self.hestia_server.id,
            'product_id': self.product.id,
        })
        account.action_provision()
        return account

    def test_deploy_requires_an_account(self):
        with self.assertRaises(UserError):
            self.domain.action_deploy_to_hestiacp()

    def test_deploy_requires_an_active_account(self):
        self._mock_hestia_client(_user_info('janecustomer'))
        account = self._provisioned_account()
        account.action_suspend()
        self.domain.hestiacp_account_id = account

        with self.assertRaises(UserError):
            self.domain.action_deploy_to_hestiacp()

    def test_deploy_calls_v_add_domain_with_the_username_and_domain(self):
        client = self._mock_hestia_client(_user_info('janecustomer'))
        account = self._provisioned_account()
        self.domain.hestiacp_account_id = account

        self.domain.action_deploy_to_hestiacp()

        client.call.assert_any_call('v-add-domain', account.username, 'example.com')

    def test_deploy_blocks_when_web_domains_limit_already_reached(self):
        client = self._mock_hestia_client(
            _user_info('janecustomer', web_limit='1', web_used='1'))
        account = self._provisioned_account()
        self.domain.hestiacp_account_id = account

        with self.assertRaises(UserError):
            self.domain.action_deploy_to_hestiacp()
        self.assertFalse(any(
            c.args and c.args[0] == 'v-add-domain' for c in client.call.call_args_list))

    def test_deploy_allows_unlimited_web_domains(self):
        self._mock_hestia_client(_user_info('janecustomer', web_limit='unlimited', web_used='999'))
        account = self._provisioned_account()
        self.domain.hestiacp_account_id = account

        self.domain.action_deploy_to_hestiacp()  # should not raise

    def test_deploy_updates_nameservers_at_namecheap(self):
        self._mock_hestia_client(_user_info(
            'janecustomer', ns='ns1.hosted.example,ns2.hosted.example'))
        account = self._provisioned_account()
        self.domain.hestiacp_account_id = account

        self.domain.action_deploy_to_hestiacp()

        self.namecheap_client.call.assert_any_call(
            'namecheap.domains.dns.setCustom', SLD='example', TLD='com',
            NameServers='ns1.hosted.example,ns2.hosted.example')

    def test_deploy_without_configured_ns_still_succeeds(self):
        self._mock_hestia_client(_user_info('janecustomer', ns=''))
        account = self._provisioned_account()
        self.domain.hestiacp_account_id = account

        self.domain.action_deploy_to_hestiacp()  # should not raise

        self.assertFalse(any(
            c.args and c.args[0] == 'namecheap.domains.dns.setCustom'
            for c in self.namecheap_client.call.call_args_list))
        self.assertTrue(any(
            'NOT updated' in (msg.body or '') for msg in self.domain.message_ids))

    def test_deploy_with_dns_managed_elsewhere_still_adds_the_domain(self):
        """The use case this toggle exists for: web/mail hosted on
        HestiaCP, DNS managed elsewhere (e.g. Cloudflare, for its
        proxy/CDN features) - v-add-domain should still run, but
        Namecheap's nameservers must be left untouched.
        """
        client = self._mock_hestia_client(_user_info('janecustomer'))
        account = self._provisioned_account()
        self.domain.write({
            'hestiacp_account_id': account.id,
            'manage_dns_via_hestiacp': False,
        })

        self.domain.action_deploy_to_hestiacp()

        client.call.assert_any_call('v-add-domain', account.username, 'example.com')

    def test_deploy_with_dns_managed_elsewhere_does_not_touch_nameservers(self):
        self._mock_hestia_client(_user_info('janecustomer'))
        account = self._provisioned_account()
        self.domain.write({
            'hestiacp_account_id': account.id,
            'manage_dns_via_hestiacp': False,
        })

        self.domain.action_deploy_to_hestiacp()

        self.assertFalse(any(
            c.args and c.args[0] == 'namecheap.domains.dns.setCustom'
            for c in self.namecheap_client.call.call_args_list))
        self.assertTrue(any(
            'left as-is' in (msg.body or '') for msg in self.domain.message_ids))

    def test_deploy_defaults_to_letting_hestiacp_manage_dns(self):
        domain = self.env['namecheap.domain'].create({
            'name': 'default-dns-test.com', 'server_id': self.namecheap_server.id,
        })
        self.assertTrue(domain.manage_dns_via_hestiacp)

    def test_deploy_marks_state_and_timestamp(self):
        self._mock_hestia_client(_user_info('janecustomer'))
        account = self._provisioned_account()
        self.domain.hestiacp_account_id = account

        self.domain.action_deploy_to_hestiacp()

        self.assertEqual(self.domain.state, 'active')
        self.assertTrue(self.domain.hestiacp_deployed_on)

    # -- DKIM fetching ----------------------------------------------------

    def test_fetch_dkim_requires_a_deployed_account(self):
        with self.assertRaises(UserError):
            self.domain.action_fetch_dkim_record()

    def test_fetch_dkim_finds_the_domainkey_txt_record(self):
        self._mock_hestia_client(dns_records_json=_dns_records())
        account = self._provisioned_account()
        self.domain.hestiacp_account_id = account

        self.domain.action_fetch_dkim_record()

        self.assertEqual(self.domain.dkim_record_name, 'mail._domainkey.example.com.')
        self.assertEqual(self.domain.dkim_record_value, 'v=DKIM1; k=rsa; p=ABC123FAKEKEYDATA')

    def test_fetch_dkim_ignores_unrelated_records(self):
        self._mock_hestia_client(dns_records_json=_dns_records())
        account = self._provisioned_account()
        self.domain.hestiacp_account_id = account

        self.domain.action_fetch_dkim_record()

        self.assertNotIn('1.2.3.4', self.domain.dkim_record_value)

    def test_fetch_dkim_raises_when_no_dkim_record_exists(self):
        self._mock_hestia_client(dns_records_json=_dns_records(include_dkim=False))
        account = self._provisioned_account()
        self.domain.hestiacp_account_id = account

        with self.assertRaises(UserError):
            self.domain.action_fetch_dkim_record()

    def test_fetch_dkim_logs_a_chatter_message(self):
        self._mock_hestia_client(dns_records_json=_dns_records())
        account = self._provisioned_account()
        self.domain.hestiacp_account_id = account

        self.domain.action_fetch_dkim_record()

        self.assertTrue(any(
            'ABC123FAKEKEYDATA' in (msg.body or '') for msg in self.domain.message_ids))
