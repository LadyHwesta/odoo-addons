# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCalendarEventPremiumVideo(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'project_id': 'pid123', 'api_token': 'tok456',
        })
        cls.premium_user = cls.env['res.users'].create({
            'name': 'Dr. Jane', 'login': 'dr.jane@example.com',
            'telehealth_video_tier': 'premium',
        })
        cls.basic_user = cls.env['res.users'].create({
            'name': 'Dr. Basic', 'login': 'dr.basic@example.com',
        })

    def setUp(self):
        super().setUp()
        self.signalwire_client = MagicMock()
        patcher = patch(
            'odoo.addons.signalwire_voip.models.signalwire_server.'
            'SignalWireServer._get_client', return_value=self.signalwire_client)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.signalwire_client.compat_post.return_value = {'sid': 'sub-abc'}
        self.signalwire_client.video_post.return_value = {'id': 'room-1'}

    def _event(self, user):
        return self.env['calendar.event'].create({
            'name': 'Consultation', 'user_id': user.id,
            'start': fields.Datetime.now(), 'stop': fields.Datetime.now(),
        })

    def test_premium_user_gets_a_telehealth_join_url(self):
        event = self._event(self.premium_user)

        event._set_discuss_videocall_location()

        self.assertIn('/telehealth/signalwire/join/', event.videocall_location)
        self.assertNotIn('calendar/join_videocall', event.videocall_location)

    def test_basic_user_still_gets_discuss(self):
        event = self._event(self.basic_user)

        event._set_discuss_videocall_location()

        self.assertIn('calendar/join_videocall', event.videocall_location)

    def test_provisioning_creates_a_real_room(self):
        event = self._event(self.premium_user)

        event._set_discuss_videocall_location()

        self.signalwire_client.video_post.assert_called_once()
        args, kwargs = self.signalwire_client.video_post.call_args
        self.assertEqual(args[0], 'rooms')
        self.assertTrue(event.signalwire_room_name)
        self.assertEqual(event.signalwire_room_id, 'room-1')

    def test_provisioning_also_sets_up_the_providers_billing(self):
        event = self._event(self.premium_user)

        event._set_discuss_videocall_location()

        self.assertTrue(self.premium_user.signalwire_video_subproject_id)
        self.assertTrue(self.premium_user.signalwire_video_contract_id)

    def test_requesting_a_link_twice_reuses_the_same_room(self):
        event = self._event(self.premium_user)
        event._set_discuss_videocall_location()
        first_room = event.signalwire_room_name

        event.videocall_location = False
        event._set_discuss_videocall_location()

        self.assertEqual(event.signalwire_room_name, first_room)
        self.signalwire_client.video_post.assert_called_once()

    def test_no_server_configured_falls_back_to_discuss(self):
        self.env['signalwire.server'].search([]).unlink()
        event = self._event(self.premium_user)

        event._set_discuss_videocall_location()

        self.assertIn('calendar/join_videocall', event.videocall_location)
