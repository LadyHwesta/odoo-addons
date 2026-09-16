# -*- coding: utf-8 -*-
from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestInboundCallController(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test SignalWire',
            'space': 'example.signalwire.com',
            'project_id': 'pid123',
            'api_token': 'tok456',
        })
        cls.subproject = cls.env['signalwire.subproject'].create({
            'name': 'Internal Team', 'server_id': cls.server.id,
            'account_sid': 'sub-abc', 'state': 'active',
        })
        cls.user = cls.env['res.users'].create({
            'name': 'Jane Agent', 'login': 'jane.agent@example.com',
            'voip_username': 'user_jane',
        })
        cls.number = cls.env['signalwire.phone_number'].create({
            'name': '+12084449665', 'sid': 'pn-123',
            'subproject_id': cls.subproject.id, 'assigned_user_id': cls.user.id,
        })

    def test_inbound_call_to_an_assigned_number_dials_its_users_sip_uri(self):
        response = self.url_open(
            '/signalwire/voice/inbound', data={'To': '+12084449665', 'From': '+15551234567'})

        self.assertEqual(response.status_code, 200)
        body = response.text
        self.assertIn('<Dial ', body)
        self.assertIn('sip:user_jane@example.sip.signalwire.com', body)

    def test_dial_carries_a_timeout_and_a_fallback_action_url(self):
        response = self.url_open(
            '/signalwire/voice/inbound', data={'To': '+12084449665', 'From': '+15551234567'})

        body = response.text
        self.assertIn('timeout="20"', body)
        self.assertIn(f'/signalwire/voice/fallback/{self.user.id}/{self.number.id}', body)

    def test_inbound_call_to_an_unknown_number_is_rejected(self):
        response = self.url_open(
            '/signalwire/voice/inbound', data={'To': '+19995550000', 'From': '+15551234567'})

        self.assertEqual(response.status_code, 200)
        self.assertIn('<Reject', response.text)

    def test_inbound_call_to_an_unassigned_number_is_rejected(self):
        self.number.assigned_user_id = False

        response = self.url_open(
            '/signalwire/voice/inbound', data={'To': '+12084449665', 'From': '+15551234567'})

        self.assertIn('<Reject', response.text)

    def test_a_desk_phone_rings_alongside_the_softphone(self):
        self.env['signalwire.desk_phone'].create({
            'user_id': self.user.id, 'name': 'Front Desk',
            'mac_address': 'aabbccddeeff', 'brand': 'yealink',
            'signalwire_sip_endpoint_id': 'ep-desk-1',
            'signalwire_server_id': self.server.id,
            'voip_username': 'deskphone_front',
        })

        response = self.url_open(
            '/signalwire/voice/inbound', data={'To': '+12084449665', 'From': '+15551234567'})

        body = response.text
        self.assertEqual(body.count('<Sip>'), 2)
        self.assertIn('sip:user_jane@example.sip.signalwire.com', body)
        self.assertIn('sip:deskphone_front@example.sip.signalwire.com', body)

    def test_desk_phone_only_user_with_no_softphone_still_rings(self):
        self.user.voip_username = False
        self.env['signalwire.desk_phone'].create({
            'user_id': self.user.id, 'name': 'Front Desk',
            'mac_address': 'aabbccddeeff', 'brand': 'yealink',
            'signalwire_sip_endpoint_id': 'ep-desk-1',
            'signalwire_server_id': self.server.id,
            'voip_username': 'deskphone_front',
        })

        response = self.url_open(
            '/signalwire/voice/inbound', data={'To': '+12084449665', 'From': '+15551234567'})

        body = response.text
        self.assertEqual(body.count('<Sip>'), 1)
        self.assertIn('sip:deskphone_front@example.sip.signalwire.com', body)
