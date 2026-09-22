# -*- coding: utf-8 -*-
from datetime import datetime
from unittest.mock import patch

from odoo.fields import Datetime
from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestInboundCallController(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test SignalWire',
            'space': 'example.signalwire.com',
            'sip_domain': 'example-abc123.sip.signalwire.com',
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
        self.assertIn('sip:user_jane@example-abc123.sip.signalwire.com', body)

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
        self.assertIn('sip:user_jane@example-abc123.sip.signalwire.com', body)
        self.assertIn('sip:deskphone_front@example-abc123.sip.signalwire.com', body)

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
        self.assertIn('sip:deskphone_front@example-abc123.sip.signalwire.com', body)

    def test_inbound_call_to_a_group_routed_number_dials_every_member(self):
        teammate = self.env['res.users'].create({
            'name': 'Bob Agent', 'login': 'bob.agent@example.com',
            'voip_username': 'user_bob',
        })
        group = self.env['signalwire.call.group'].create({
            'name': 'Sales', 'member_ids': [(6, 0, [self.user.id, teammate.id])],
        })
        self.number.write({'route_type': 'group', 'call_group_id': group.id})

        response = self.url_open(
            '/signalwire/voice/inbound', data={'To': '+12084449665', 'From': '+15551234567'})

        body = response.text
        self.assertIn('sip:user_jane@example-abc123.sip.signalwire.com', body)
        self.assertIn('sip:user_bob@example-abc123.sip.signalwire.com', body)
        self.assertIn(f'/signalwire/voice/group_fallback/{group.id}/{self.number.id}', body)

    def test_group_fallback_with_no_answer_and_no_voicemail_user_apologizes(self):
        group = self.env['signalwire.call.group'].create({
            'name': 'Sales', 'member_ids': [(6, 0, [self.user.id])],
        })

        response = self.url_open(
            f'/signalwire/voice/group_fallback/{group.id}/{self.number.id}',
            data={'DialCallStatus': 'no-answer'})

        self.assertIn('<Say>', response.text)
        self.assertNotIn('<Record', response.text)

    def test_group_fallback_with_no_answer_and_a_voicemail_user_records_one(self):
        voicemail_user = self.env['res.users'].create({
            'name': 'Voicemail Catcher', 'login': 'catcher@example.com'})
        group = self.env['signalwire.call.group'].create({
            'name': 'Sales', 'member_ids': [(6, 0, [self.user.id])],
            'voicemail_mode': 'user', 'voicemail_user_id': voicemail_user.id,
        })

        response = self.url_open(
            f'/signalwire/voice/group_fallback/{group.id}/{self.number.id}',
            data={'DialCallStatus': 'no-answer'})

        self.assertIn(
            f'/signalwire/voice/voicemail_complete/{voicemail_user.id}/{self.number.id}',
            response.text)

    def test_group_fallback_with_no_answer_and_a_shared_group_box_records_one(self):
        group = self.env['signalwire.call.group'].create({
            'name': 'Sales', 'member_ids': [(6, 0, [self.user.id])],
            'voicemail_mode': 'group',
        })

        response = self.url_open(
            f'/signalwire/voice/group_fallback/{group.id}/{self.number.id}',
            data={'DialCallStatus': 'no-answer'})

        self.assertIn('<Record', response.text)
        self.assertIn(
            f'/signalwire/voice/group_voicemail_complete/{group.id}/{self.number.id}',
            response.text)

    def test_group_fallback_when_the_call_completed_does_nothing_further(self):
        group = self.env['signalwire.call.group'].create({
            'name': 'Sales', 'member_ids': [(6, 0, [self.user.id])],
        })

        response = self.url_open(
            f'/signalwire/voice/group_fallback/{group.id}/{self.number.id}',
            data={'DialCallStatus': 'completed'})

        self.assertNotIn('<Say', response.text)
        self.assertNotIn('<Record', response.text)

    def test_inbound_call_to_an_ivr_routed_number_gathers_a_digit(self):
        menu = self.env['signalwire.ivr.menu'].create({
            'name': 'Main Menu', 'greeting_text': 'Press 1 for sales.'})
        self.number.write({'route_type': 'ivr', 'ivr_menu_id': menu.id})

        response = self.url_open(
            '/signalwire/voice/inbound', data={'To': '+12084449665', 'From': '+15551234567'})

        body = response.text
        self.assertIn('<Gather', body)
        self.assertIn('Press 1 for sales.', body)
        self.assertIn(f'/signalwire/voice/ivr/{menu.id}/{self.number.id}/digit', body)

    def test_ivr_digit_rings_the_targeted_user(self):
        menu = self.env['signalwire.ivr.menu'].create({
            'name': 'Main Menu', 'greeting_text': 'Press 1 for sales.'})
        self.env['signalwire.ivr.menu.option'].create({
            'menu_id': menu.id, 'digit': '1', 'action_type': 'user',
            'target_user_id': self.user.id,
        })

        response = self.url_open(
            f'/signalwire/voice/ivr/{menu.id}/{self.number.id}/digit', data={'Digits': '1'})

        self.assertIn('sip:user_jane@example-abc123.sip.signalwire.com', response.text)

    def test_ivr_digit_rings_the_targeted_group(self):
        menu = self.env['signalwire.ivr.menu'].create({
            'name': 'Main Menu', 'greeting_text': 'Press 2 for support.'})
        group = self.env['signalwire.call.group'].create({
            'name': 'Support', 'member_ids': [(6, 0, [self.user.id])]})
        self.env['signalwire.ivr.menu.option'].create({
            'menu_id': menu.id, 'digit': '2', 'action_type': 'group',
            'target_call_group_id': group.id,
        })

        response = self.url_open(
            f'/signalwire/voice/ivr/{menu.id}/{self.number.id}/digit', data={'Digits': '2'})

        self.assertIn('sip:user_jane@example-abc123.sip.signalwire.com', response.text)
        self.assertIn(f'/signalwire/voice/group_fallback/{group.id}/{self.number.id}',
                       response.text)

    def test_ivr_digit_takes_a_voicemail(self):
        menu = self.env['signalwire.ivr.menu'].create({
            'name': 'Main Menu', 'greeting_text': 'Press 3 to leave a message.'})
        self.env['signalwire.ivr.menu.option'].create({
            'menu_id': menu.id, 'digit': '3', 'action_type': 'voicemail',
            'target_user_id': self.user.id,
        })

        response = self.url_open(
            f'/signalwire/voice/ivr/{menu.id}/{self.number.id}/digit', data={'Digits': '3'})

        self.assertIn('<Record', response.text)
        self.assertIn(
            f'/signalwire/voice/voicemail_complete/{self.user.id}/{self.number.id}',
            response.text)

    def test_ivr_digit_hangs_up(self):
        menu = self.env['signalwire.ivr.menu'].create({
            'name': 'Main Menu', 'greeting_text': 'Press 9 to hang up.'})
        self.env['signalwire.ivr.menu.option'].create({
            'menu_id': menu.id, 'digit': '9', 'action_type': 'hangup'})

        response = self.url_open(
            f'/signalwire/voice/ivr/{menu.id}/{self.number.id}/digit', data={'Digits': '9'})

        self.assertIn('<Hangup', response.text)

    def test_ivr_digit_enters_a_submenu(self):
        submenu = self.env['signalwire.ivr.menu'].create({
            'name': 'Sales Submenu', 'greeting_text': 'Press 1 for new sales.'})
        menu = self.env['signalwire.ivr.menu'].create({
            'name': 'Main Menu', 'greeting_text': 'Press 4 for sales.'})
        self.env['signalwire.ivr.menu.option'].create({
            'menu_id': menu.id, 'digit': '4', 'action_type': 'submenu',
            'target_submenu_id': submenu.id,
        })

        response = self.url_open(
            f'/signalwire/voice/ivr/{menu.id}/{self.number.id}/digit', data={'Digits': '4'})

        self.assertIn('Press 1 for new sales.', response.text)
        self.assertIn(f'/signalwire/voice/ivr/{submenu.id}/{self.number.id}/digit', response.text)

    def test_ivr_digit_with_no_match_reprompts_the_same_menu(self):
        menu = self.env['signalwire.ivr.menu'].create({
            'name': 'Main Menu', 'greeting_text': 'Press 1 for sales.'})
        self.env['signalwire.ivr.menu.option'].create({
            'menu_id': menu.id, 'digit': '1', 'action_type': 'hangup'})

        response = self.url_open(
            f'/signalwire/voice/ivr/{menu.id}/{self.number.id}/digit', data={'Digits': '5'})

        self.assertIn('not a valid option', response.text)
        self.assertIn('Press 1 for sales.', response.text)

    def test_inbound_call_with_a_call_sid_creates_a_live_call(self):
        self.url_open('/signalwire/voice/inbound', data={
            'To': '+12084449665', 'From': '+15551234567', 'CallSid': 'CA999'})

        live_call = self.env['signalwire.live_call'].search([('call_sid', '=', 'CA999')])
        self.assertTrue(live_call)
        self.assertEqual(live_call.state, 'ringing')
        self.assertEqual(live_call.from_number, '+15551234567')
        self.assertEqual(live_call.assigned_user_id, self.user)

    def test_inbound_call_without_a_call_sid_creates_no_live_call(self):
        before = self.env['signalwire.live_call'].search_count([])

        self.url_open(
            '/signalwire/voice/inbound', data={'To': '+12084449665', 'From': '+15551234567'})

        self.assertEqual(self.env['signalwire.live_call'].search_count([]), before)

    def test_fallback_completed_marks_the_live_call_ended(self):
        self.env['signalwire.live_call'].create({
            'call_sid': 'CA888', 'phone_number_id': self.number.id,
            'from_number': '+15551234567', 'assigned_user_id': self.user.id,
        })

        self.url_open(
            f'/signalwire/voice/fallback/{self.user.id}/{self.number.id}',
            data={'DialCallStatus': 'completed', 'CallSid': 'CA888'})

        live_call = self.env['signalwire.live_call'].search([('call_sid', '=', 'CA888')])
        self.assertEqual(live_call.state, 'ended')

    def test_route_to_user_dials_that_users_sip_uri(self):
        response = self.url_open(
            f'/signalwire/voice/route_to_user/{self.user.id}/{self.number.id}', data={'CallSid': 'CA000'})

        self.assertIn('sip:user_jane@example-abc123.sip.signalwire.com', response.text)

    def test_route_to_voicemail_records_a_message(self):
        response = self.url_open(
            f'/signalwire/voice/route_to_voicemail/{self.user.id}/{self.number.id}', data={'CallSid': 'CA000'})

        self.assertIn('<Record', response.text)
        self.assertIn(
            f'/signalwire/voice/voicemail_complete/{self.user.id}/{self.number.id}',
            response.text)

    def test_route_to_voicemail_uses_the_default_greeting_and_settings(self):
        response = self.url_open(
            f'/signalwire/voice/route_to_voicemail/{self.user.id}/{self.number.id}', data={'CallSid': 'CA000'})

        body = response.text
        self.assertIn('<Say>Please leave a message after the tone.</Say>', body)
        self.assertIn('maxLength="120"', body)
        self.assertIn('playBeep="true"', body)

    def test_route_to_voicemail_uses_the_users_own_custom_greeting_text(self):
        self.user.signalwire_voicemail_greeting_text = "Hi, you've reached Jane. Leave a note!"

        response = self.url_open(
            f'/signalwire/voice/route_to_voicemail/{self.user.id}/{self.number.id}', data={'CallSid': 'CA000'})

        self.assertIn(
            "<Say>Hi, you've reached Jane. Leave a note!</Say>", response.text)

    def test_route_to_voicemail_uses_the_users_own_max_length_and_beep(self):
        self.user.write({
            'signalwire_voicemail_max_length': 60, 'signalwire_voicemail_beep': False})

        response = self.url_open(
            f'/signalwire/voice/route_to_voicemail/{self.user.id}/{self.number.id}', data={'CallSid': 'CA000'})

        body = response.text
        self.assertIn('maxLength="60"', body)
        self.assertIn('playBeep="false"', body)

    def test_route_to_voicemail_plays_a_custom_recorded_greeting_when_set(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'web.base.url', 'https://odoo.example.com')
        self.user.signalwire_voicemail_greeting = 'ZmFrZS1hdWRpbw=='  # base64 "fake-audio"
        attachment = self.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'res.users'), ('res_id', '=', self.user.id),
            ('res_field', '=', 'signalwire_voicemail_greeting'),
        ])
        self.assertTrue(attachment)

        response = self.url_open(
            f'/signalwire/voice/route_to_voicemail/{self.user.id}/{self.number.id}', data={'CallSid': 'CA000'})

        self.assertIn(
            f'<Play>https://odoo.example.com/signalwire/voice/greeting/{attachment.id}</Play>',
            response.text)
        self.assertNotIn('<Say>', response.text)

    def test_voice_greeting_serves_the_attachment(self):
        self.user.signalwire_voicemail_greeting = 'ZmFrZS1hdWRpbw=='
        attachment = self.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'res.users'), ('res_id', '=', self.user.id),
            ('res_field', '=', 'signalwire_voicemail_greeting'),
        ])

        response = self.url_open(f'/signalwire/voice/greeting/{attachment.id}')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'fake-audio')

    def test_voice_greeting_404s_for_an_unrelated_attachment(self):
        attachment = self.env['ir.attachment'].sudo().create({
            'name': 'unrelated.txt', 'raw': b'not a greeting'})

        response = self.url_open(f'/signalwire/voice/greeting/{attachment.id}')

        self.assertEqual(response.status_code, 404)

    def _with_after_hours_calendar(self, **route_vals):
        calendar = self.env['resource.calendar'].create({
            'name': 'Test Hours', 'tz': 'UTC',
            'attendance_ids': [(0, 0, {
                'name': 'All Day Monday', 'dayofweek': '0',
                'hour_from': 0.0, 'hour_to': 24.0, 'day_period': 'morning',
            })],
        })
        self.number.write({'calendar_id': calendar.id, **route_vals})

    def test_inbound_call_after_hours_straight_to_user_voicemail(self):
        self._with_after_hours_calendar(
            after_hours_route_type='user_voicemail', after_hours_user_id=self.user.id)
        sunday = Datetime.to_string(datetime(2026, 9, 20, 12, 0, 0))  # a real Sunday

        with patch('odoo.fields.Datetime.now', return_value=Datetime.from_string(sunday)):
            response = self.url_open(
                '/signalwire/voice/inbound',
                data={'To': '+12084449665', 'From': '+15551234567'})

        body = response.text
        self.assertIn('<Record', body)
        self.assertIn(
            f'/signalwire/voice/voicemail_complete/{self.user.id}/{self.number.id}', body)
        self.assertNotIn('<Dial', body)

    def test_inbound_call_after_hours_straight_to_group_voicemail(self):
        group = self.env['signalwire.call.group'].create({'name': 'Sales'})
        self._with_after_hours_calendar(
            after_hours_route_type='group_voicemail', after_hours_call_group_id=group.id)
        sunday = Datetime.to_string(datetime(2026, 9, 20, 12, 0, 0))  # a real Sunday

        with patch('odoo.fields.Datetime.now', return_value=Datetime.from_string(sunday)):
            response = self.url_open(
                '/signalwire/voice/inbound',
                data={'To': '+12084449665', 'From': '+15551234567'})

        body = response.text
        self.assertIn('<Record', body)
        self.assertIn(
            f'/signalwire/voice/group_voicemail_complete/{group.id}/{self.number.id}', body)
        self.assertNotIn('<Dial', body)

    def test_hold_loop_plays_a_message_and_pauses(self):
        response = self.url_open(
            f'/signalwire/voice/hold_loop/{self.number.id}', data={'CallSid': 'CA000'})

        self.assertIn('<Say>', response.text)
        self.assertIn('<Pause', response.text)
