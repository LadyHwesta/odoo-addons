# -*- coding: utf-8 -*-
from unittest import mock

import requests

from odoo.tests.common import TransactionCase, tagged

_DELIVERY = 'odoo.addons.activitypub.models.activitypub_delivery'


@tagged('post_install', '-at_install')
class TestDelivery(TransactionCase):

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
        cls.env['activitypub.follower'].create({
            'actor_id': cls.actor.id,
            'follower_uri': 'https://remote.example/users/bob',
            'inbox_url': 'https://remote.example/users/bob/inbox',
            'shared_inbox_url': 'https://remote.example/inbox',
            'state': 'accepted',
        })
        cls.partner = cls.env.user.partner_id

    def _publish(self):
        return self.actor._ap_publish(
            'res.partner', self.partner.id, 'Note', {'content': 'hi'})

    def _run_cron(self):
        self.env['activitypub.delivery']._cron_deliver()

    def test_publish_queues_one_delivery_to_shared_inbox(self):
        activity = self._publish()
        self.assertEqual(len(activity.delivery_ids), 1)
        self.assertEqual(activity.delivery_ids.inbox_url, 'https://remote.example/inbox')
        self.assertEqual(activity.delivery_ids.state, 'pending')
        self.assertEqual(activity.state, 'pending')

    def test_delivered_on_2xx(self):
        activity = self._publish()
        with mock.patch(_DELIVERY + '.post_activity', return_value=(202, 'ok')) as posted:
            self._run_cron()
        posted.assert_called_once()
        self.assertEqual(activity.delivery_ids.state, 'delivered')
        self.assertEqual(activity.state, 'delivered')

    def test_5xx_schedules_retry(self):
        activity = self._publish()
        with mock.patch(_DELIVERY + '.post_activity', return_value=(503, 'later')):
            self._run_cron()
        delivery = activity.delivery_ids
        self.assertEqual(delivery.state, 'retry')
        self.assertEqual(delivery.attempts, 1)
        self.assertTrue(delivery.next_attempt)
        self.assertEqual(activity.state, 'pending')

    def test_4xx_fails_permanently(self):
        activity = self._publish()
        with mock.patch(_DELIVERY + '.post_activity', return_value=(403, 'no')):
            self._run_cron()
        self.assertEqual(activity.delivery_ids.state, 'failed')
        self.assertEqual(activity.state, 'failed')

    def test_network_error_schedules_retry(self):
        activity = self._publish()
        with mock.patch(_DELIVERY + '.post_activity',
                        side_effect=requests.ConnectionError('down')):
            self._run_cron()
        self.assertEqual(activity.delivery_ids.state, 'retry')
        self.assertEqual(activity.delivery_ids.attempts, 1)

    def test_retry_not_picked_up_before_next_attempt(self):
        activity = self._publish()
        with mock.patch(_DELIVERY + '.post_activity', return_value=(500, 'x')):
            self._run_cron()
        # Second run in the same instant must not touch it again.
        with mock.patch(_DELIVERY + '.post_activity', return_value=(200, 'ok')) as posted:
            self._run_cron()
        posted.assert_not_called()
        self.assertEqual(activity.delivery_ids.attempts, 1)

    def test_no_followers_marks_activity_delivered(self):
        self.actor.follower_ids.unlink()
        activity = self.actor._ap_publish(
            'res.partner', self.partner.id, 'Note', {'content': 'lonely'})
        self.assertFalse(activity.delivery_ids)
        self.assertEqual(activity.state, 'delivered')
