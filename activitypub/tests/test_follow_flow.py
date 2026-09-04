# -*- coding: utf-8 -*-
from unittest import mock

from odoo import fields
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.activitypub.models.activitypub_service import SignatureError

_ACTIVITY = 'odoo.addons.activitypub.models.activitypub_activity'
BOB = 'https://remote.example/users/bob'
BOB_KEY = BOB + '#main-key'


@tagged('post_install', '-at_install')
class TestFollowFlow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.website = cls.env['website'].search([], limit=1)
        cls.website.domain = 'https://news.example.com'
        cls.actor = cls.env['activitypub.actor'].create({
            'website_id': cls.website.id,
            'actor_type': 'Service',
            'username': 'news',
            'name': 'News',
        })

    def _seed_remote(self):
        # A fresh cache row means activitypub.remote.actor._get returns it
        # without any HTTP fetch. Idempotent so repeated _ingest calls are OK.
        RemoteActor = self.env['activitypub.remote.actor']
        vals = {
            'uri': BOB,
            'inbox_url': BOB + '/inbox',
            'shared_inbox_url': 'https://remote.example/inbox',
            'public_key_pem': 'PEM-PLACEHOLDER',
            'key_id': BOB_KEY,
            'fetched_at': fields.Datetime.now(),
        }
        existing = RemoteActor.search([('uri', '=', BOB)], limit=1)
        if existing:
            existing.write(vals)
            return existing
        return RemoteActor.create(vals)

    def _ingest(self, raw, sig_return=None, sig_error=None):
        self._seed_remote()
        patch_kw = {}
        if sig_error is not None:
            patch_kw['side_effect'] = sig_error
        else:
            patch_kw['return_value'] = sig_return or {'keyId': BOB_KEY}
        with mock.patch(_ACTIVITY + '.verify_signature', **patch_kw):
            return self.env['activitypub.activity']._ingest(
                raw, {'signature': 'x'},
                '/ap/actors/%d/inbox' % self.actor.id, b'{}', self.actor)

    def _follow_payload(self):
        return {
            'type': 'Follow',
            'id': 'https://remote.example/f/1',
            'actor': BOB,
            'object': self.actor.actor_url,
        }

    # ------------------------------------------------------------------
    def test_follow_creates_follower_and_sends_accept(self):
        status = self._ingest(self._follow_payload())
        self.assertEqual(status, 202)

        follower = self.env['activitypub.follower'].search([
            ('actor_id', '=', self.actor.id)])
        self.assertEqual(len(follower), 1)
        self.assertEqual(follower.follower_uri, BOB)
        self.assertEqual(follower.shared_inbox_url, 'https://remote.example/inbox')
        self.assertEqual(self.actor.follower_count, 1)

        accept = self.env['activitypub.activity'].search([
            ('activity_type', '=', 'Accept'), ('direction', '=', 'out')])
        self.assertEqual(len(accept), 1)
        self.assertEqual(accept.payload['type'], 'Accept')
        self.assertEqual(accept.payload['object']['id'], 'https://remote.example/f/1')
        self.assertEqual(accept.delivery_ids.inbox_url, 'https://remote.example/inbox')

    def test_follow_is_idempotent(self):
        self._ingest(self._follow_payload())
        self._ingest(self._follow_payload())
        self.assertEqual(self.env['activitypub.follower'].search_count([
            ('actor_id', '=', self.actor.id)]), 1)

    def test_undo_follow_removes_follower(self):
        self._ingest(self._follow_payload())
        status = self._ingest({
            'type': 'Undo',
            'id': 'https://remote.example/u/1',
            'actor': BOB,
            'object': {'type': 'Follow', 'object': self.actor.actor_url},
        })
        self.assertEqual(status, 202)
        self.assertEqual(self.actor.follower_count, 0)

    def test_bad_signature_is_401(self):
        status = self._ingest(self._follow_payload(),
                              sig_error=SignatureError('nope'))
        self.assertEqual(status, 401)
        self.assertFalse(self.env['activitypub.follower'].search_count([
            ('actor_id', '=', self.actor.id)]))

    def test_keyid_not_owned_by_actor_is_401(self):
        status = self._ingest(self._follow_payload(),
                              sig_return={'keyId': 'https://evil.example/k#main-key'})
        self.assertEqual(status, 401)

    def test_missing_actor_is_400(self):
        status = self._ingest({'type': 'Follow', 'id': 'x',
                               'object': self.actor.actor_url})
        self.assertEqual(status, 400)

    def test_unknown_type_is_accepted_and_ignored(self):
        status = self._ingest({
            'type': 'Like', 'id': 'https://remote.example/l/1',
            'actor': BOB, 'object': 'https://news.example.com/ap/objects/1',
        })
        self.assertEqual(status, 202)
        logged = self.env['activitypub.activity'].search([
            ('direction', '=', 'in'), ('activity_type', '=', 'Like')])
        self.assertEqual(logged.state, 'ignored')
