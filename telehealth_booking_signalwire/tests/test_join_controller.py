# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo import fields
from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestJoinController(HttpCase):

    def setUp(self):
        super().setUp()
        self.signalwire_client = MagicMock()
        patcher = patch(
            'odoo.addons.signalwire_voip.models.signalwire_server.'
            'SignalWireServer._get_client', return_value=self.signalwire_client)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.signalwire_client.compat_post.return_value = {'sid': 'sub-abc'}
        self.signalwire_client.video_post.side_effect = [
            {'id': 'room-1'},  # room creation
            {'token': 'fake-jwt-room-token'},  # room token for the joiner
        ]

        self.server = self.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'project_id': 'pid123', 'api_token': 'tok456',
        })
        self.premium_user = self.env['res.users'].create({
            'name': 'Dr. Jane', 'login': 'dr.jane@example.com',
            'telehealth_video_tier': 'premium',
        })
        self.event = self.env['calendar.event'].create({
            'name': 'Consultation', 'user_id': self.premium_user.id,
            'start': fields.Datetime.now(), 'stop': fields.Datetime.now(),
        })
        self.event._set_discuss_videocall_location()

    def test_join_page_generates_a_fresh_room_token(self):
        response = self.url_open(self.event.videocall_location.replace(
            self.env['calendar.event'].get_base_url(), ''))

        self.assertEqual(response.status_code, 200)
        self.assertIn('fake-jwt-room-token', response.text)
        # the room-creation call was the first video_post; the token
        # request is the second, made fresh on this very request
        self.assertEqual(self.signalwire_client.video_post.call_count, 2)
        token_call = self.signalwire_client.video_post.call_args_list[1]
        self.assertEqual(token_call.args[0], 'room_tokens')
        self.assertEqual(token_call.kwargs['room_name'], self.event.signalwire_room_name)

    def test_unknown_token_404s(self):
        response = self.url_open('/telehealth/signalwire/join/not-a-real-token')
        self.assertEqual(response.status_code, 404)

    def test_visiting_twice_generates_two_fresh_tokens(self):
        path = self.event.videocall_location.replace(
            self.env['calendar.event'].get_base_url(), '')
        self.url_open(path)
        self.signalwire_client.video_post.side_effect = [{'token': 'second-token'}]

        response = self.url_open(path)

        self.assertIn('second-token', response.text)
