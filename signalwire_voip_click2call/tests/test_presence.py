# -*- coding: utf-8 -*-
from odoo.service.model import call_kw
from odoo.tests.common import HttpCase, tagged

SIP = 'example-abc123.sip.signalwire.com'


@tagged('post_install', '-at_install')
class TestPresence(HttpCase):
    """Away skips a person, Mobile rings their app and mobile number with a
    press-1 check, and a receptionist can still ring someone who's Away."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param('web.base.url', 'https://odoo.example.com')
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'sip_domain': SIP, 'project_id': 'pid123', 'api_token': 'tok456',
        })
        cls.subproject = cls.env['signalwire.subproject'].create({
            'name': 'Internal Team', 'server_id': cls.server.id,
            'account_sid': 'sub-abc', 'state': 'active',
        })
        cls.jane = cls.env['res.users'].create({
            'name': 'Jane Agent', 'login': 'jane.presence@example.com',
            'voip_username': 'user_jane',
        })
        cls.bob = cls.env['res.users'].create({
            'name': 'Bob Agent', 'login': 'bob.presence@example.com',
            'voip_username': 'user_bob',
        })
        cls.number = cls.env['signalwire.phone_number'].create({
            'name': '+12084449665', 'sid': 'pn-123',
            'subproject_id': cls.subproject.id, 'assigned_user_id': cls.jane.id,
        })
        cls.group = cls.env['signalwire.call.group'].create({
            'name': 'Front Desk', 'member_ids': [(6, 0, [cls.jane.id, cls.bob.id])],
        })
        cls.group_number = cls.env['signalwire.phone_number'].create({
            'name': '+12084449666', 'sid': 'pn-456', 'subproject_id': cls.subproject.id,
            'route_type': 'group', 'call_group_id': cls.group.id,
        })

    def _inbound(self, to='+12084449665'):
        return self.url_open('/signalwire/voice/inbound', data={
            'To': to, 'From': '+15551234567', 'CallSid': 'CA-1'}).text

    def test_presence_is_set_the_way_the_browser_sets_it(self):
        call_kw(self.env['res.users'].with_user(self.jane), 'set_signalwire_presence', ['away'], {})
        self.assertEqual(self.jane.signalwire_presence, 'away')
        call_kw(self.env['res.users'].with_user(self.jane), 'set_signalwire_presence', ['nonsense'], {})
        self.assertEqual(self.jane.signalwire_presence, 'away')

    def test_away_skips_straight_to_voicemail(self):
        self.jane.signalwire_presence = 'away'
        body = self._inbound()
        self.assertNotIn('<Sip', body)
        self.assertIn('<Record', body)

    def test_available_rings_as_before(self):
        self.assertIn(f'sip:user_jane@{SIP}', self._inbound())

    def test_group_skips_whoever_is_away(self):
        self.jane.signalwire_presence = 'away'
        body = self._inbound('+12084449666')
        self.assertNotIn('user_jane', body)
        self.assertIn(f'sip:user_bob@{SIP}', body)

    def test_all_away_group_puts_the_caller_in_its_queue(self):
        (self.jane | self.bob).write({'signalwire_presence': 'away'})
        self.group.write({'voicemail_mode': 'user', 'voicemail_user_id': self.jane.id})
        body = self._inbound('+12084449666')
        self.assertNotIn('<Sip', body)
        self.assertIn('/signalwire/voice/queue_choice/', body)
        self.assertIn('press 2', body)

    def test_mobile_rings_app_and_mobile_number_with_a_screen(self):
        cell = self.env['signalwire.forwarding.number'].create({
            'user_id': self.jane.id, 'name': 'Cell', 'phone_number': '+15559876543'})
        self.env['signalwire.desk_phone'].create({
            'user_id': self.jane.id, 'name': 'Desk', 'mac_address': 'aabbccdd0011',
            'brand': 'yealink', 'signalwire_sip_endpoint_id': 'ep-1',
            'signalwire_server_id': self.server.id, 'voip_username': 'desk_jane'})
        self.jane.write({'signalwire_presence': 'mobile', 'signalwire_mobile_forward_id': cell.id})
        body = self._inbound()
        self.assertIn(f'sip:user_jane@{SIP}', body)
        self.assertNotIn('desk_jane', body)
        self.assertIn('+15559876543</Number>', body)
        self.assertIn(
            f'url="https://odoo.example.com/signalwire/voice/screen/{self.jane.id}'
            '?caller=%2B15551234567"', body)

    def test_screen_asks_for_1_and_only_1_connects(self):
        body = self.url_open(
            f'/signalwire/voice/screen/{self.jane.id}?caller=%2B15551234567', data={'CallSid': 'CA-leg'}).text
        self.assertIn('<Gather numDigits="1"', body)
        self.assertIn('1 5 5 5 1 2 3 4 5 6 7', body)
        self.assertNotIn('<Hangup', self.url_open(
            '/signalwire/voice/screen_answer', data={'Digits': '1'}).text)
        self.assertIn('<Hangup', self.url_open(
            '/signalwire/voice/screen_answer', data={'Digits': '9'}).text)
        self.assertIn('<Hangup', self.url_open('/signalwire/voice/screen_answer', data={'CallSid': 'CA-leg'}).text)

    def test_receptionist_can_still_ring_someone_away(self):
        self.jane.signalwire_presence = 'away'
        body = self.url_open(
            f'/signalwire/voice/route_to_user/{self.jane.id}/{self.number.id}', data={'CallSid': 'CA-1'}).text
        self.assertIn(f'sip:user_jane@{SIP}', body)

    def test_ring_group_step_skips_away_teammates(self):
        self.jane.signalwire_ring_group_ids = [(6, 0, [self.bob.id])]
        self.bob.signalwire_presence = 'away'
        body = self.url_open(
            f'/signalwire/voice/fallback/{self.jane.id}/{self.number.id}',
            data={'DialCallStatus': 'no-answer'}).text
        self.assertNotIn('user_bob', body)
        self.assertIn('<Record', body)
