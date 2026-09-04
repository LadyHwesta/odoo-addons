# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from odoo.tests.common import TransactionCase, tagged

PUBLIC = 'https://www.w3.org/ns/activitystreams#Public'


@tagged('post_install', '-at_install')
class TestEventFederation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.website = cls.env['website'].search([], limit=1)
        cls.website.domain = 'https://events.example.com'
        cls.actor = cls.env['activitypub.actor'].create({
            'website_id': cls.website.id,
            'actor_type': 'Group',
            'username': 'events',
            'display_name': 'What\'s On',
        })
        cls.etype = cls.env['event.type'].create({
            'name': 'Meetups',
            'activitypub_actor_id': cls.actor.id,
        })
        cls.env['activitypub.follower'].create({
            'actor_id': cls.actor.id,
            'follower_uri': 'https://remote.example/users/bob',
            'shared_inbox_url': 'https://remote.example/inbox',
            'state': 'accepted',
        })
        cls.begin = datetime(2026, 6, 1, 18, 0, 0)
        cls.end = datetime(2026, 6, 1, 20, 0, 0)

    def _make(self, name='Launch party', published=True, **vals):
        return self.env['event.event'].create(dict({
            'name': name,
            'event_type_id': self.etype.id,
            'date_begin': self.begin,
            'date_end': self.end,
            'website_published': published,
        }, **vals))

    def _object(self, event):
        return self.env['activitypub.object'].search([
            ('source_model', '=', 'event.event'),
            ('source_res_id', '=', event.id),
        ], limit=1)

    def _activities(self, event, activity_type=None):
        obj = self._object(event)
        domain = [('object_id', '=', obj.id)]
        if activity_type:
            domain.append(('activity_type', '=', activity_type))
        return self.env['activitypub.activity'].search(domain)

    # ------------------------------------------------------------------
    def test_category_actor_is_inherited(self):
        event = self._make(published=False)
        self.assertEqual(event.activitypub_actor_id, self.actor)

    def test_publish_creates_event_object(self):
        event = self._make()
        obj = self._object(event)
        self.assertTrue(obj)
        self.assertEqual(obj.object_type, 'Event')
        self.assertEqual(obj.payload['type'], 'Event')
        self.assertEqual(obj.payload['attributedTo'], self.actor.actor_url)
        self.assertEqual(obj.payload['to'], [PUBLIC])
        self.assertEqual(obj.payload['startTime'], '2026-06-01T18:00:00Z')
        self.assertEqual(obj.payload['endTime'], '2026-06-01T20:00:00Z')
        create = self._activities(event, 'Create')
        self.assertEqual(len(create), 1)
        self.assertEqual(create.delivery_ids.inbox_url, 'https://remote.example/inbox')

    def test_location_is_a_place(self):
        venue = self.env['res.partner'].create({
            'name': 'The Big Hall', 'city': 'Vilnius'})
        event = self._make(address_id=venue.id)
        place = self._object(event).payload.get('location')
        self.assertTrue(place)
        self.assertEqual(place['type'], 'Place')
        self.assertIn('Big Hall', place['name'])

    def test_edit_dates_sends_update(self):
        event = self._make()
        event.write({'date_end': self.end + timedelta(hours=1)})
        self.assertTrue(self._activities(event, 'Update'))
        self.assertEqual(self._object(event).payload['endTime'], '2026-06-01T21:00:00Z')

    def test_unpublish_sends_delete(self):
        event = self._make()
        event.write({'website_published': False})
        self.assertTrue(self._activities(event, 'Delete'))
        self.assertTrue(self._object(event).deleted)

    def test_unpublished_event_does_not_federate(self):
        event = self._make(published=False)
        self.assertFalse(self._object(event))

    def test_per_event_actor_override(self):
        other = self.env['activitypub.actor'].create({
            'website_id': self.website.id, 'actor_type': 'Group',
            'username': 'special', 'display_name': 'Special',
        })
        event = self._make(activitypub_actor_id=other.id)
        self.assertEqual(self._object(event).payload['attributedTo'], other.actor_url)
