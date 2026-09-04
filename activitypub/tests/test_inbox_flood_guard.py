# -*- coding: utf-8 -*-
from unittest import mock

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.activitypub.models.activitypub_service import ActivityPubError

_ACTIVITY = 'odoo.addons.activitypub.models.activitypub_activity'


@tagged('post_install', '-at_install')
class TestInboxAttemptModel(TransactionCase):
    """The counter itself, independent of _ingest."""

    def test_not_flooding_below_threshold(self):
        Attempt = self.env['activitypub.inbox.attempt']
        for _ in range(4):
            Attempt._record('evil.example')
        self.assertFalse(Attempt._is_flooding('evil.example', 60, 5))

    def test_flooding_at_threshold(self):
        Attempt = self.env['activitypub.inbox.attempt']
        for _ in range(5):
            Attempt._record('evil.example')
        self.assertTrue(Attempt._is_flooding('evil.example', 60, 5))

    def test_hosts_counted_independently(self):
        Attempt = self.env['activitypub.inbox.attempt']
        for _ in range(5):
            Attempt._record('a.example')
        self.assertFalse(Attempt._is_flooding('b.example', 60, 5))


@tagged('post_install', '-at_install')
class TestIngestRateLimiting(TransactionCase):
    """The guard fires before any dereference - it must bound a flood using
    forged/unverifiable actor claims, not just already-authenticated ones."""

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

    def _raw(self, i):
        return {
            'type': 'Follow',
            'id': f'https://flood.example/f/{i}',
            'actor': f'https://flood.example/actors/{i}',
            'object': self.actor.actor_url,
        }

    def test_flood_of_unverifiable_actors_is_capped_before_any_fetch(self):
        RemoteActorModel = type(self.env['activitypub.remote.actor'])
        calls = []

        def fake_get(remote_self, uri, force_refresh=False):
            calls.append(uri)
            raise ActivityPubError('cannot dereference')

        # _record() and _is_flooding() both run inside one _ingest() call, in
        # that order - the Nth recorded attempt is the one that trips the
        # limit, so exactly limit - 1 attempts get dereferenced before it.
        limit = 3
        with mock.patch.object(RemoteActorModel, '_get', fake_get), \
             mock.patch(_ACTIVITY + '.INBOUND_RATE_LIMIT', limit):
            for i in range(limit - 1):
                status = self.env['activitypub.activity']._ingest(
                    self._raw(i), {'signature': 'x'}, '/ap/inbox', b'{}')
                self.assertEqual(status, 401)
            self.assertEqual(len(calls), limit - 1,
                             "each distinct actor should still have been "
                             "dereferenced below the limit")

            # The limit-th attempt, and any after it from the same host, are
            # rejected before touching the network at all.
            for i in range(limit - 1, limit + 2):
                status = self.env['activitypub.activity']._ingest(
                    self._raw(i), {'signature': 'x'}, '/ap/inbox', b'{}')
                self.assertEqual(status, 429)
            self.assertEqual(len(calls), limit - 1,
                             "none of the rate-limited attempts should have "
                             "been dereferenced")
