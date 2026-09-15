# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestNamecheapDomain(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['namecheap.server'].create({
            'name': 'Test Namecheap',
            'api_user': 'tester', 'api_key': 'key123', 'username': 'tester',
            'client_ip': '1.2.3.4', 'sandbox': True,
        })

    def _mock_client(self):
        mock_client = MagicMock()
        patcher = patch(
            'odoo.addons.namecheap_domains.models.namecheap_server.'
            'NamecheapServer._get_client',
            return_value=mock_client)
        patcher.start()
        self.addCleanup(patcher.stop)
        return mock_client

    def test_tld_is_computed_from_the_domain_name(self):
        domain = self.env['namecheap.domain'].create({
            'name': 'example.com', 'server_id': self.server.id,
        })
        self.assertEqual(domain.tld, 'com')

    def test_defaults_to_draft(self):
        domain = self.env['namecheap.domain'].create({
            'name': 'example.net', 'server_id': self.server.id,
        })
        self.assertEqual(domain.state, 'draft')

    def test_cannot_track_the_same_domain_twice(self):
        self.env['namecheap.domain'].create({
            'name': 'dupe.com', 'server_id': self.server.id,
        })
        with self.assertRaises(Exception):
            self.env['namecheap.domain'].create({
                'name': 'dupe.com', 'server_id': self.server.id,
            })
            self.env.cr.flush()

    def test_update_nameservers_requires_a_value(self):
        domain = self.env['namecheap.domain'].create({
            'name': 'example.org', 'server_id': self.server.id,
        })
        with self.assertRaises(UserError):
            domain.action_update_nameservers()

    def test_update_nameservers_calls_set_custom_nameservers(self):
        client = self._mock_client()
        domain = self.env['namecheap.domain'].create({
            'name': 'example.org', 'server_id': self.server.id,
            'nameservers': 'ns1.cloudflare.com, ns2.cloudflare.com',
        })

        domain.action_update_nameservers()

        client.call.assert_called_once_with(
            'namecheap.domains.dns.setCustom', SLD='example', TLD='org',
            NameServers='ns1.cloudflare.com,ns2.cloudflare.com')

    def test_update_nameservers_logs_a_chatter_message(self):
        self._mock_client()
        domain = self.env['namecheap.domain'].create({
            'name': 'example.org', 'server_id': self.server.id,
            'nameservers': 'ns1.cloudflare.com,ns2.cloudflare.com',
        })

        domain.action_update_nameservers()

        self.assertTrue(any(
            'ns1.cloudflare.com' in (msg.body or '') for msg in domain.message_ids))
