# -*- coding: utf-8 -*-
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
