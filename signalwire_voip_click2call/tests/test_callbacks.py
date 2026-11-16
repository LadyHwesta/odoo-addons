# -*- coding: utf-8 -*-
import json
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.service.model import call_kw
from odoo.tests.common import HttpCase, tagged

SIP = 'example-abc123.sip.signalwire.com'
ALERT = 'signalwire_callback/alert'


@tagged('post_install', '-at_install')
class TestCallbackRequests(HttpCase):
    """A caller on hold presses 1, the person they wanted is alerted when
    free, and can call now or book it in the calendar."""

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
        user_group = cls.env.ref('base.group_user')
        cls.jane = cls.env['res.users'].create({
            'name': 'Jane Agent', 'login': 'jane.cb@example.com', 'voip_username': 'user_jane',
            'group_ids': [(6, 0, [user_group.id])]})
        cls.bob = cls.env['res.users'].create({
            'name': 'Bob Agent', 'login': 'bob.cb@example.com', 'voip_username': 'user_bob',
            'group_ids': [(6, 0, [user_group.id])]})
        cls.outsider = cls.env['res.users'].create({
            'name': 'Not Involved', 'login': 'outsider.cb@example.com',
            'group_ids': [(6, 0, [user_group.id])]})
        cls.group = cls.env['signalwire.call.group'].create({
            'name': 'Sales', 'member_ids': [(6, 0, [cls.jane.id, cls.bob.id])],
            'max_ring_attempts': 2})
        cls.number = cls.env['signalwire.phone_number'].create({
            'name': '+12084449666', 'sid': 'pn-456', 'subproject_id': cls.subproject.id,
            'route_type': 'group', 'call_group_id': cls.group.id})
        cls.customer = cls.env['res.partner'].create({
            'name': 'Carla Customer', 'phone': '+1 (555) 123-4567', 'email': 'carla@example.com'})

    def _alerts_for(self, user):
        # Bus messages are only written when the transaction commits.
        self.env.cr.precommit.run()
        alerts = []
        for bus in self.env['bus.bus'].sudo().search([]):
            channel, message = json.loads(bus.channel), json.loads(bus.message)
            if channel[-2:] == ['res.partner', user.partner_id.id] and message.get('type') == ALERT:
                alerts.append(message)
        return alerts

    # ---- the offer while on hold ----

    def test_group_hold_offers_a_callback(self):
        body = self.url_open(f'/signalwire/voice/group_fallback/{self.group.id}/{self.number.id}', data={
            'DialCallStatus': 'no-answer', 'From': '+15551234567', 'CallSid': 'CA-1'}).text
        self.assertIn(f'action="/signalwire/voice/callback_offer/group/{self.group.id}/{self.number.id}?attempt=1"', body)
        self.assertIn('press 1', body)
        self.assertIn('<Dial', body)  # no key pressed: rings again, as before

    def test_no_offer_when_caller_id_is_withheld(self):
        body = self.url_open(f'/signalwire/voice/group_fallback/{self.group.id}/{self.number.id}', data={
            'DialCallStatus': 'no-answer', 'From': 'anonymous', 'CallSid': 'CA-1'}).text
        self.assertNotIn('callback_offer', body)

    def test_pressing_1_records_the_request_and_hangs_up(self):
        live = self.env['signalwire.live_call'].create({
            'call_sid': 'CA-1', 'phone_number_id': self.number.id, 'from_number': '+15551234567'})
        body = self.url_open(
            f'/signalwire/voice/callback_offer/group/{self.group.id}/{self.number.id}?attempt=1',
            data={'Digits': '1', 'From': '+15551234567', 'CallSid': 'CA-1'}).text
        self.assertIn('call you back', body)
        self.assertIn('<Hangup', body)
        request = self.env['signalwire.callback_request'].search([('live_call_id', '=', live.id)])
        self.assertEqual(request.source, 'phone')
        self.assertEqual(request.target_group_id, self.group)
        self.assertEqual(request.partner_id, self.customer)
        live.invalidate_recordset()
        self.assertEqual(live.state, 'ended')

    def test_another_key_carries_on_ringing(self):
        body = self.url_open(
            f'/signalwire/voice/callback_offer/group/{self.group.id}/{self.number.id}?attempt=1',
            data={'Digits': '5', 'From': '+15551234567', 'CallSid': 'CA-1'}).text
        self.assertIn(f'sip:user_jane@{SIP}', body)
        self.assertFalse(self.env['signalwire.callback_request'].search([('phone_number', '=', '+15551234567')]))

    def test_check_first_hold_offers_a_callback_for_that_colleague(self):
        body = self.url_open(f'/signalwire/voice/hold_loop/{self.number.id}?user={self.jane.id}', data={
            'From': '+15551234567', 'CallSid': 'CA-1'}).text
        self.assertIn(f'callback_offer/hold/{self.jane.id}/{self.number.id}', body)
        self.assertIn(f'hold_loop/{self.number.id}?user={self.jane.id}', body)

    # ---- alerts ----

    def test_free_people_are_alerted_and_busy_ones_when_free(self):
        self.bob.write({'signalwire_call_state': 'on_call',
                        'signalwire_call_state_at': fields.Datetime.now()})
        request = self.env['signalwire.callback_request'].create({
            'source': 'phone', 'phone_number': '+15551234567', 'target_group_id': self.group.id})
        self.assertEqual([a['payload']['id'] for a in self._alerts_for(self.jane)], [request.id])
        self.assertFalse(self._alerts_for(self.bob))
        call_kw(self.env['res.users'].with_user(self.bob), 'set_signalwire_call_state', ['idle'], {})
        self.assertEqual([a['payload']['id'] for a in self._alerts_for(self.bob)], [request.id])

    def test_coming_back_from_away_alerts(self):
        self.jane.signalwire_presence = 'away'
        self.env['signalwire.callback_request'].create({
            'source': 'phone', 'phone_number': '+15551234567', 'target_user_id': self.jane.id})
        self.assertFalse(self._alerts_for(self.jane))
        call_kw(self.env['res.users'].with_user(self.jane), 'set_signalwire_presence', ['available'], {})
        self.assertTrue(self._alerts_for(self.jane))

    # ---- acting on it ----

    def test_call_now_returns_the_number_and_only_once(self):
        request = self.env['signalwire.callback_request'].create({
            'source': 'phone', 'phone_number': '+15551234567', 'target_group_id': self.group.id})
        Requests = self.env['signalwire.callback_request']
        number = call_kw(Requests.with_user(self.jane), 'action_call_now', [[request.id]], {})
        self.assertEqual(number, '+15551234567')
        self.assertEqual(request.state, 'completed')
        with self.assertRaises(UserError):
            call_kw(Requests.with_user(self.bob), 'action_call_now', [[request.id]], {})

    def test_schedule_books_the_calendar_without_emailing_anyone(self):
        request = self.env['signalwire.callback_request'].create({
            'source': 'phone', 'phone_number': '+15551234567',
            'partner_id': self.customer.id, 'target_user_id': self.jane.id})
        mails_before = self.env['mail.mail'].sudo().search_count([])
        start = fields.Datetime.now() + timedelta(days=1)
        event_id = call_kw(self.env['signalwire.callback_request'].with_user(self.jane),
                           'schedule_signalwire_callback', [{
                               'request_id': request.id, 'user_id': self.jane.id,
                               'start': fields.Datetime.to_string(start), 'duration': 30,
                               'note': 'Quote follow-up'}], {})
        event = self.env['calendar.event'].browse(event_id)
        self.assertEqual(event.name, 'Callback: Carla Customer')
        self.assertEqual(event.partner_ids, self.jane.partner_id | self.customer)
        self.assertEqual(event.stop - event.start, timedelta(minutes=30))
        self.assertEqual(request.state, 'scheduled')
        self.assertEqual(request.event_id, event)
        self.assertEqual(self.env['mail.mail'].sudo().search_count([]), mails_before)

    def test_receptionist_books_a_new_callback_from_scratch(self):
        start = fields.Datetime.now() + timedelta(hours=3)
        event_id = self.env['signalwire.callback_request'].schedule_signalwire_callback({
            'user_id': self.bob.id, 'start': fields.Datetime.to_string(start),
            'phone_number': '+15559990000', 'note': 'Wants a quote'})
        request = self.env['signalwire.callback_request'].search([('event_id', '=', event_id)])
        self.assertEqual(request.source, 'receptionist')
        self.assertEqual(request.target_user_id, self.bob)
        self.assertEqual(request.state, 'scheduled')

    # ---- who sees what ----

    def test_people_see_only_requests_for_them(self):
        request = self.env['signalwire.callback_request'].create({
            'source': 'phone', 'phone_number': '+15551234567', 'target_group_id': self.group.id})
        Requests = self.env['signalwire.callback_request']
        self.assertTrue(Requests.with_user(self.bob).search([('id', '=', request.id)]))
        self.assertFalse(Requests.with_user(self.outsider).search([('id', '=', request.id)]))
        with self.assertRaises(AccessError):
            request.with_user(self.outsider).read(['phone_number'])
