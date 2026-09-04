# -*- coding: utf-8 -*-
from datetime import datetime
from unittest import mock

from odoo import fields
from odoo.tests.common import TransactionCase, tagged

_ACTIVITY = 'odoo.addons.activitypub.models.activitypub_activity'
BOB = 'https://remote.example/users/bob'
BOB_KEY = BOB + '#main-key'
NOTE = 'https://remote.example/notes/1'


@tagged('post_install', '-at_install')
class TestInboundInteraction(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.website = cls.env['website'].search([], limit=1)
        cls.website.domain = 'https://news.example.com'
        cls.actor = cls.env['activitypub.actor'].create({
            'website_id': cls.website.id,
            'actor_type': 'Service',
            'username': 'news',
            'display_name': 'News',
        })
        cls.target = cls.env['res.partner'].create({'name': 'Federated Target'})
        cls.actor._ap_publish('res.partner', cls.target.id, 'Note',
                              {'content': 'original'})
        cls.local = cls.env['activitypub.object'].search([
            ('source_model', '=', 'res.partner'),
            ('source_res_id', '=', cls.target.id),
        ], limit=1)

    def _seed_remote(self):
        RemoteActor = self.env['activitypub.remote.actor']
        vals = {
            'uri': BOB,
            'inbox_url': BOB + '/inbox',
            'shared_inbox_url': 'https://remote.example/inbox',
            'public_key_pem': 'PEM-PLACEHOLDER',
            'key_id': BOB_KEY,
            'preferred_username': 'bob',
            'domain': 'remote.example',
            'fetched_at': fields.Datetime.now(),
        }
        existing = RemoteActor.search([('uri', '=', BOB)], limit=1)
        if existing:
            existing.write(vals)
            return existing
        return RemoteActor.create(vals)

    def _ingest(self, raw):
        self._seed_remote()
        with mock.patch(_ACTIVITY + '.verify_signature',
                        return_value={'keyId': BOB_KEY}):
            return self.env['activitypub.activity']._ingest(
                raw, {'signature': 'x'},
                '/ap/actors/%d/inbox' % self.actor.id, b'{}', self.actor)

    def _reply(self, content='<p>nice post</p>', note_id=NOTE):
        return {
            'type': 'Create',
            'id': 'https://remote.example/create/1',
            'actor': BOB,
            'object': {
                'id': note_id,
                'type': 'Note',
                'content': content,
                'inReplyTo': self.local.uri,
                'published': '2026-01-02T03:04:05Z',
                'url': 'https://remote.example/@bob/1',
            },
        }

    def _stored(self, uri=NOTE):
        return self.env['activitypub.object'].search([('uri', '=', uri)], limit=1)

    # ------------------------------------------------------------------
    def test_reply_stored_and_threaded(self):
        self.assertEqual(self._ingest(self._reply()), 202)
        stored = self._stored()
        self.assertTrue(stored)
        self.assertFalse(stored.local)
        self.assertEqual(stored.in_reply_to_uri, self.local.uri)
        self.assertEqual(stored.published, datetime(2026, 1, 2, 3, 4, 5))
        self.local.invalidate_recordset(['reply_count'])
        self.assertEqual(self.local.reply_count, 1)

    def test_reply_posted_to_chatter(self):
        before = len(self.target.message_ids)
        self._ingest(self._reply(content='<p>hello there</p>'))
        self.target.invalidate_recordset(['message_ids'])
        self.assertEqual(len(self.target.message_ids), before + 1)
        body = self.target.message_ids[0].body
        self.assertIn('hello there', body)
        self.assertIn('@bob@remote.example', body)

    def test_reply_to_unknown_object_is_ignored(self):
        raw = self._reply()
        raw['object']['inReplyTo'] = 'https://news.example.com/ap/objects/999999'
        self.assertEqual(self._ingest(raw), 202)
        self.assertFalse(self._stored())

    def test_duplicate_reply_not_double_posted(self):
        self._ingest(self._reply())
        self.target.invalidate_recordset(['message_ids'])
        before = len(self.target.message_ids)
        self._ingest(self._reply())
        self.target.invalidate_recordset(['message_ids'])
        self.assertEqual(len(self.target.message_ids), before)
        self.assertEqual(self.env['activitypub.object'].search_count(
            [('uri', '=', NOTE)]), 1)

    def test_chatter_toggle_off_still_stores(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'activitypub.replies_to_chatter', 'False')
        before = len(self.target.message_ids)
        self._ingest(self._reply())
        self.target.invalidate_recordset(['message_ids'])
        self.assertEqual(len(self.target.message_ids), before)
        self.assertTrue(self._stored())

    def test_like_and_announce_are_counted(self):
        self._ingest({'type': 'Like', 'id': 'https://remote.example/like/1',
                      'actor': BOB, 'object': self.local.uri})
        self._ingest({'type': 'Announce', 'id': 'https://remote.example/ann/1',
                      'actor': BOB, 'object': self.local.uri})
        self.local.invalidate_recordset(['like_count', 'announce_count'])
        self.assertEqual(self.local.like_count, 1)
        self.assertEqual(self.local.announce_count, 1)

    def test_like_is_idempotent(self):
        for _ in range(2):
            self._ingest({'type': 'Like', 'id': 'https://remote.example/like/1',
                          'actor': BOB, 'object': self.local.uri})
        self.assertEqual(self.env['activitypub.interaction'].search_count([
            ('object_id', '=', self.local.id),
            ('interaction_type', '=', 'like')]), 1)

    def test_undo_like_decrements(self):
        self._ingest({'type': 'Like', 'id': 'https://remote.example/like/1',
                      'actor': BOB, 'object': self.local.uri})
        self._ingest({
            'type': 'Undo', 'id': 'https://remote.example/undo/1', 'actor': BOB,
            'object': {'type': 'Like', 'id': 'https://remote.example/like/1',
                       'object': self.local.uri},
        })
        self.local.invalidate_recordset(['like_count'])
        self.assertEqual(self.local.like_count, 0)

    def test_like_on_unknown_object_is_ignored(self):
        status = self._ingest({
            'type': 'Like', 'id': 'x', 'actor': BOB,
            'object': 'https://news.example.com/ap/objects/999999'})
        self.assertEqual(status, 202)
        self.assertEqual(self.env['activitypub.interaction'].search_count(
            [('object_id', '=', self.local.id)]), 0)

    def test_remote_update_refreshes_stored_object(self):
        self._ingest(self._reply(content='<p>v1</p>'))
        self._ingest({
            'type': 'Update', 'id': 'https://remote.example/upd/1', 'actor': BOB,
            'object': {'id': NOTE, 'type': 'Note', 'content': '<p>v2</p>',
                       'inReplyTo': self.local.uri},
        })
        self.assertIn('v2', self._stored().payload['content'])

    def test_remote_delete_tombstones_reply(self):
        self._ingest(self._reply())
        self._ingest({
            'type': 'Delete', 'id': 'https://remote.example/del/1', 'actor': BOB,
            'object': {'id': NOTE, 'type': 'Tombstone'},
        })
        self.assertTrue(self._stored().deleted)
        self.local.invalidate_recordset(['reply_count'])
        self.assertEqual(self.local.reply_count, 0)

    def test_remote_actor_self_delete_drops_follower(self):
        self.env['activitypub.follower'].create({
            'actor_id': self.actor.id, 'follower_uri': BOB, 'state': 'accepted'})
        self._ingest({'type': 'Delete', 'id': 'https://remote.example/del/self',
                      'actor': BOB, 'object': BOB})
        self.assertEqual(self.actor.follower_count, 0)
