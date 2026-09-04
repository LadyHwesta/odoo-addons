# -*- coding: utf-8 -*-
from unittest import mock

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.activitypub.models.activitypub_service import RemoteFetchError

_REMOTE = 'odoo.addons.activitypub.models.activitypub_remote_actor'


def _doc(id_uri, **extra):
    doc = {
        'id': id_uri,
        'inbox': id_uri + '/inbox',
        'preferredUsername': 'bob',
        'publicKey': {'id': id_uri + '#main-key', 'publicKeyPem': 'PEM'},
        'endpoints': {'sharedInbox': 'https://remote.example/inbox'},
    }
    doc.update(extra)
    return doc


@tagged('post_install', '-at_install')
class TestRemoteActorCache(TransactionCase):

    def test_get_caches_by_the_fetched_uri(self):
        uri = 'https://remote.example/users/bob'
        with mock.patch(_REMOTE + '.fetch_json', return_value=_doc(uri)):
            record = self.env['activitypub.remote.actor']._get(uri)
        self.assertEqual(record.uri, uri)
        self.assertEqual(record.public_key_pem, 'PEM')

    def test_mismatched_declared_id_is_rejected(self):
        # The identity-spoofing vector: a real, correctly-fetchable actor
        # whose own document claims to *be* a completely different actor.
        fetch_uri = 'https://attacker.example/actors/1'
        claimed_id = 'https://victim.example/actors/1'
        with mock.patch(_REMOTE + '.fetch_json', return_value=_doc(claimed_id)):
            with self.assertRaises(RemoteFetchError):
                self.env['activitypub.remote.actor']._get(fetch_uri)
        # Neither identity should have been cached from a rejected fetch.
        self.assertFalse(self.env['activitypub.remote.actor'].search([
            '|', ('uri', '=', fetch_uri), ('uri', '=', claimed_id)]))

    def test_missing_id_falls_back_to_fetch_uri(self):
        # Non-compliant (id is mandatory in AS2) but not malicious - a
        # document that simply omits `id` still gets cached by the URL we
        # actually fetched.
        uri = 'https://remote.example/users/carol'
        doc = _doc(uri)
        doc.pop('id')
        with mock.patch(_REMOTE + '.fetch_json', return_value=doc):
            record = self.env['activitypub.remote.actor']._get(uri)
        self.assertEqual(record.uri, uri)
