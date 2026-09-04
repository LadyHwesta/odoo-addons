# -*- coding: utf-8 -*-
from cryptography.hazmat.primitives.serialization import load_pem_private_key

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestActivityPubActor(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.website = cls.env['website'].search([], limit=1)
        cls.website.domain = 'https://news.example.com'
        cls.Actor = cls.env['activitypub.actor']

    def _make(self, **vals):
        return self.Actor.create(dict({
            'website_id': self.website.id,
            'actor_type': 'Service',
            'username': 'news',
            'name': 'Example News',
        }, **vals))

    def test_keypair_generated_on_create(self):
        actor = self._make()
        self.assertTrue(actor.public_key_pem.startswith('-----BEGIN PUBLIC KEY-----'))
        # private key is readable here (test user is superuser) and parseable
        priv = actor.private_key_pem
        self.assertTrue(priv)
        load_pem_private_key(priv.encode(), password=None)

    def test_urls_derive_from_website_domain(self):
        actor = self._make()
        self.assertEqual(actor.domain, 'news.example.com')
        self.assertEqual(actor.handle, '@news@news.example.com')
        self.assertEqual(actor.actor_url,
                         f'https://news.example.com/ap/actors/{actor.id}')
        self.assertEqual(actor._endpoint('/inbox'),
                         f'https://news.example.com/ap/actors/{actor.id}/inbox')
        self.assertEqual(actor._shared_inbox_url(),
                         'https://news.example.com/ap/inbox')

    def test_username_is_lowercased(self):
        actor = self._make(username='NewsRoom')
        self.assertEqual(actor.username, 'newsroom')

    def test_invalid_username_rejected(self):
        with self.assertRaises(ValidationError):
            self._make(username='news room')

    def test_username_unique_per_website(self):
        self._make()
        with self.assertRaises(Exception), mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                self._make(name='Another')
                self.env.flush_all()

    def test_same_username_other_website_ok(self):
        self._make()
        other = self.env['website'].create({'name': 'Branch', 'domain': 'https://branch.example.org'})
        actor2 = self._make(website_id=other.id)
        self.assertEqual(actor2.domain, 'branch.example.org')

    def test_username_locked_after_federation(self):
        actor = self._make()
        actor.username = 'renamed'  # free while it has never federated
        self.assertEqual(actor.username, 'renamed')
        actor.federated_once = True
        with self.assertRaises(ValidationError):
            actor.username = 'renamed-again'

    def test_actor_document_is_well_formed(self):
        actor = self._make(summary='<p>Daily news</p>')
        doc = actor._ap_actor_document()
        self.assertEqual(doc['id'], actor.actor_url)
        self.assertEqual(doc['preferredUsername'], 'news')
        self.assertEqual(doc['type'], 'Service')
        self.assertEqual(doc['publicKey']['publicKeyPem'], actor.public_key_pem)
        self.assertEqual(doc['summary'], '<p>Daily news</p>')

    def test_regenerate_keys_changes_pair(self):
        actor = self._make()
        before = actor.public_key_pem
        actor.action_regenerate_keys()
        self.assertNotEqual(actor.public_key_pem, before)
