# -*- coding: utf-8 -*-
from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCalendarEventTelehealth(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.basic_user = cls.env['res.users'].create({
            'name': 'Basic Provider', 'login': 'basic_provider@example.com',
        })
        cls.premium_user = cls.env['res.users'].create({
            'name': 'Premium Provider', 'login': 'premium_provider@example.com',
            'telehealth_video_tier': 'premium',
        })

    def _event(self, user):
        return self.env['calendar.event'].create({
            'name': 'Consultation', 'user_id': user.id,
            'start': fields.Datetime.now(), 'stop': fields.Datetime.now(),
        })

    def test_basic_tier_gets_a_discuss_link(self):
        event = self._event(self.basic_user)

        event._set_discuss_videocall_location()

        self.assertIn('calendar/join_videocall', event.videocall_location)

    def test_premium_tier_with_no_bridge_installed_falls_back_to_discuss(self):
        # The base module's own _get_premium_video_url is a no-op - it
        # always returns False, so premium-tier users get exactly the
        # same Discuss link as basic ones until a bridge module
        # actually implements the hook.
        event = self._event(self.premium_user)

        event._set_discuss_videocall_location()

        self.assertIn('calendar/join_videocall', event.videocall_location)

    def test_get_premium_video_url_is_a_noop_by_default(self):
        event = self._event(self.premium_user)
        self.assertFalse(event._get_premium_video_url())

    def test_action_get_telehealth_video_link_sets_the_location(self):
        event = self._event(self.basic_user)
        self.assertFalse(event.videocall_location)

        event.action_get_telehealth_video_link()

        self.assertTrue(event.videocall_location)

    def test_mixed_batch_of_basic_and_premium_events_both_resolve(self):
        events = self._event(self.basic_user) | self._event(self.premium_user)

        events._set_discuss_videocall_location()

        self.assertTrue(all(events.mapped('videocall_location')))
