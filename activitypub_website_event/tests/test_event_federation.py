# -*- coding: utf-8 -*-
from datetime import date, datetime, timedelta
from unittest.mock import Mock

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
            'name': 'What\'s On',
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
        # base_geolocalize isn't installed here, so the partner has no
        # date_localization at all - coordinates must be omitted, not
        # defaulted to (0, 0).
        self.assertNotIn('latitude', place)

    def test_place_includes_a_real_zero_zero_coordinate(self):
        # partner_latitude/longitude default to 0.0 when never geocoded -
        # indistinguishable from a genuine (0, 0) by value alone.
        # date_localization (base_geolocalize) is what actually tells them
        # apart, so exercise the logic directly against a double that has
        # it, without pulling base_geolocalize in as a real dependency.
        fake_self = Mock()
        fake_self.address_inline = False
        fake_self.address_id = Mock(
            display_name='Null Island HQ', partner_latitude=0.0,
            partner_longitude=0.0, date_localization=date(2026, 1, 1))
        place_method = type(self.env['event.event'])._ap_place
        place = place_method(fake_self)
        self.assertEqual(place['latitude'], 0.0)
        self.assertEqual(place['longitude'], 0.0)

    def test_place_omits_coordinates_when_never_geocoded(self):
        fake_self = Mock()
        fake_self.address_inline = False
        fake_self.address_id = Mock(
            display_name='Somewhere', partner_latitude=0.0,
            partner_longitude=0.0, date_localization=False)
        place_method = type(self.env['event.event'])._ap_place
        place = place_method(fake_self)
        self.assertNotIn('latitude', place)
        self.assertNotIn('longitude', place)

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
            'username': 'special', 'name': 'Special',
        })
        event = self._make(activitypub_actor_id=other.id)
        self.assertEqual(self._object(event).payload['attributedTo'], other.actor_url)

    def test_setting_category_actor_alone_does_not_write_the_event(self):
        # Setting event.type.activitypub_actor_id is a write on event.type,
        # never on event.event, so it must not by itself trigger _ap_sync()
        # for events under that category - _ap_actor()'s live fallback
        # means they'd federate correctly the *next* time something does
        # sync them (an edit, or the catch-up cron), without needing this
        # assignment to reach into every event under the category.
        empty_type = self.env['event.type'].create({'name': 'No actor yet'})
        event = self._make(event_type_id=empty_type.id)
        self.assertFalse(self._object(event), "no category actor: nothing to federate")

        empty_type.activitypub_actor_id = self.actor.id
        self.assertFalse(self._object(event), "assigning the category's actor "
                                              "must not itself sync the event")
        self.assertEqual(event._ap_actor(), self.actor, "but resolution "
                                                        "already sees it live")

    def test_reset_action_reapplies_category_actor(self):
        empty_type = self.env['event.type'].create({'name': 'Fixed later'})
        event = self._make(event_type_id=empty_type.id)
        self.assertFalse(event.activitypub_actor_id)

        empty_type.activitypub_actor_id = self.actor.id
        event.action_reset_activitypub_actor()
        self.assertEqual(event.activitypub_actor_id, self.actor)

    def test_catch_up_federates_event_once_actor_configured_late(self):
        empty_type = self.env['event.type'].create({'name': 'Was empty'})
        event = self._make(event_type_id=empty_type.id)
        self.assertFalse(self._object(event))

        empty_type.activitypub_actor_id = self.actor.id
        self.assertFalse(self._object(event), "setting the category actor "
                                              "alone must not federate yet")

        self.env['event.event']._cron_federate_catch_up()
        self.assertTrue(self._object(event))
        self.assertTrue(self._activities(event, 'Create'))

    def test_catch_up_does_not_touch_already_federated_events(self):
        event = self._make()
        first_activity = self._activities(event, 'Create')
        self.assertEqual(len(first_activity), 1)

        self.env['event.event']._cron_federate_catch_up()
        self.assertEqual(self._activities(event, 'Create'), first_activity)
