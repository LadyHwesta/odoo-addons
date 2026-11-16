# -*- coding: utf-8 -*-
import json
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.service.model import call_kw
from odoo.tests.common import HttpCase, tagged

SIP = 'example-abc123.sip.signalwire.com'
REDIRECT = ('odoo.addons.signalwire_voip_click2call.models.signalwire_live_call.'
            'SignalWireLiveCall._redirect')


@tagged('post_install', '-at_install')
class TestCallQueue(HttpCase):
    """Nobody is refused: callers wait in a call group's queue or one
    person's own, and are offered one agent at a time, longest-free first."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param('web.base.url', 'https://odoo.example.com')
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'sip_domain': SIP, 'project_id': 'pid123', 'api_token': 'tok456'})
        cls.subproject = cls.env['signalwire.subproject'].create({
            'name': 'Internal Team', 'server_id': cls.server.id,
            'account_sid': 'sub-abc', 'state': 'active'})
        internal = [(6, 0, [cls.env.ref('base.group_user').id])]
        cls.jane = cls.env['res.users'].create({
            'name': 'Jane Agent', 'login': 'jane.q@example.com', 'voip_username': 'user_jane',
            'group_ids': internal})
        cls.bob = cls.env['res.users'].create({
            'name': 'Bob Agent', 'login': 'bob.q@example.com', 'voip_username': 'user_bob',
            'group_ids': internal})
        cls.group = cls.env['signalwire.call.group'].create({
            'name': 'Sales', 'member_ids': [(6, 0, [cls.jane.id, cls.bob.id])],
            'voicemail_mode': 'group'})
        cls.number = cls.env['signalwire.phone_number'].create({
            'name': '+12084449666', 'sid': 'pn-q', 'subproject_id': cls.subproject.id,
            'route_type': 'group', 'call_group_id': cls.group.id})
        cls.direct = cls.env['signalwire.phone_number'].create({
            'name': '+12084449667', 'sid': 'pn-q2', 'subproject_id': cls.subproject.id,
            'assigned_user_id': cls.jane.id})

    def setUp(self):
        super().setUp()
        now = fields.Datetime.now()
        # Jane has been free longer than Bob.
        self.jane.write({'signalwire_call_state': 'idle',
                         'signalwire_call_state_at': now - timedelta(minutes=30)})
        self.bob.write({'signalwire_call_state': 'idle',
                        'signalwire_call_state_at': now - timedelta(minutes=5)})
        # Only this patch: patch.stopall would also undo the test
        # framework's own patches and break later tests.
        self.redirect = self.startPatcher(patch(REDIRECT))

    def _busy(self, *users):
        for user in users:
            user.write({'signalwire_call_state': 'on_call',
                        'signalwire_call_state_at': fields.Datetime.now()})

    def _call(self, sid, caller='+15551234567', to='+12084449666'):
        return self.url_open('/signalwire/voice/inbound', data={
            'To': to, 'From': caller, 'CallSid': sid}).text

    def _live(self, sid):
        return self.env['signalwire.live_call'].search([('call_sid', '=', sid)])

    # ---- Situation 1: a call group ----

    def test_offered_to_the_agent_free_the_longest_only(self):
        body = self._call('CA-1')
        self.assertIn(f'sip:user_jane@{SIP}', body)
        self.assertNotIn('user_bob', body)
        call = self._live('CA-1')
        self.assertIn(f'/signalwire/voice/queue_result/{call.id}', body)
        self.assertEqual((call.state, call.offer_user_id), ('ringing', self.jane))
        self.assertEqual(self.jane.signalwire_call_state, 'ringing')

    def test_a_second_caller_goes_to_the_next_free_agent(self):
        self._call('CA-1')
        body = self._call('CA-2', caller='+15559990000')
        self.assertIn(f'sip:user_bob@{SIP}', body)
        self.assertNotIn('user_jane', body)

    def test_everyone_busy_means_waiting_in_line_with_options(self):
        self._busy(self.jane, self.bob)
        first = self._call('CA-1')
        self.assertNotIn('<Sip', first)
        self.assertIn('You are next in line.', first)
        self.assertIn('press 1', first)
        self.assertIn('press 2', first)
        second = self._call('CA-2', caller='+15559990000')
        self.assertIn('You are caller number 2 in line.', second)

    def test_no_caller_id_means_no_callback_option(self):
        self._busy(self.jane, self.bob)
        body = self._call('CA-1', caller='anonymous')
        self.assertNotIn('press 1', body)
        self.assertIn('press 2', body)

    def test_away_and_busy_agents_are_skipped(self):
        self.jane.signalwire_presence = 'away'
        self._busy(self.bob)
        self.assertNotIn('<Sip', self._call('CA-1'))

    # ---- an agent who doesn't answer ----

    def test_missed_offer_keeps_the_place_and_tries_someone_else(self):
        self._call('CA-1')
        call = self._live('CA-1')
        place = call.queued_at
        body = self.url_open(f'/signalwire/voice/queue_result/{call.id}', data={
            'DialCallStatus': 'no-answer', 'CallSid': 'CA-1', 'From': '+15551234567'}).text
        self.assertIn(f'sip:user_bob@{SIP}', body)
        call.invalidate_recordset()
        self.assertEqual(call.queued_at, place)
        self.assertEqual(call.last_missed_user_id, self.jane)
        self.assertEqual(self.jane.signalwire_call_state, 'idle')  # left Available

    def test_the_only_agent_who_missed_is_not_rung_again_straight_away(self):
        self._busy(self.bob)
        self._call('CA-1')
        call = self._live('CA-1')
        body = self.url_open(f'/signalwire/voice/queue_result/{call.id}', data={
            'DialCallStatus': 'no-answer', 'CallSid': 'CA-1', 'From': '+15551234567'}).text
        self.assertNotIn('<Sip', body)
        self.assertIn('/signalwire/voice/queue_choice/', body)

    def test_answered_call_ends_the_queue_entry(self):
        self._call('CA-1')
        call = self._live('CA-1')
        self.url_open(f'/signalwire/voice/queue_result/{call.id}', data={
            'DialCallStatus': 'completed', 'CallSid': 'CA-1'})
        call.invalidate_recordset()
        self.assertEqual(call.state, 'ended')

    # ---- choices while waiting ----

    def _waiting(self, sid='CA-1'):
        self._busy(self.jane, self.bob)
        self._call(sid)
        return self._live(sid)

    def test_press_1_for_a_callback(self):
        call = self._waiting()
        body = self.url_open(f'/signalwire/voice/queue_choice/{call.id}', data={
            'Digits': '1', 'CallSid': 'CA-1', 'From': '+15551234567'}).text
        self.assertIn('call you back', body)
        request = self.env['signalwire.callback_request'].search([('live_call_id', '=', call.id)])
        self.assertEqual(request.target_group_id, self.group)
        call.invalidate_recordset()
        self.assertEqual(call.state, 'ended')

    def test_press_2_for_the_groups_voicemail(self):
        call = self._waiting()
        body = self.url_open(f'/signalwire/voice/queue_choice/{call.id}', data={
            'Digits': '2', 'CallSid': 'CA-1', 'From': '+15551234567'}).text
        self.assertIn(f'/signalwire/voice/group_voicemail_complete/{self.group.id}', body)

    def test_any_other_key_keeps_waiting(self):
        call = self._waiting()
        body = self.url_open(f'/signalwire/voice/queue_choice/{call.id}', data={
            'Digits': '7', 'CallSid': 'CA-1', 'From': '+15551234567'}).text
        self.assertIn(f'/signalwire/voice/queue_wait/{call.id}', body)
        call.invalidate_recordset()
        self.assertEqual(call.state, 'queued')

    # ---- someone becomes free ----

    def test_hanging_up_offers_the_longest_waiting_caller(self):
        first = self._waiting('CA-1')
        self._call('CA-2', caller='+15559990000')
        call_kw(self.env['res.users'].with_user(self.bob), 'set_signalwire_call_state', ['idle'], {})
        first.invalidate_recordset()
        self.assertEqual((first.state, first.offer_user_id), ('ringing', self.bob))
        self.redirect.assert_called_once_with(f'/signalwire/voice/queue_connect/{first.id}')
        body = self.url_open(f'/signalwire/voice/queue_connect/{first.id}', data={
            'CallSid': 'CA-1', 'From': '+15551234567'}).text
        self.assertIn(f'sip:user_bob@{SIP}', body)

    def test_personal_queue_comes_before_the_group_queue(self):
        group_caller = self._waiting('CA-1')
        personal = self.env['signalwire.live_call'].create({
            'call_sid': 'CA-P', 'phone_number_id': self.number.id, 'from_number': '+15550001111'})
        personal._queue_join(user=self.bob)  # joined later than the group caller
        call_kw(self.env['res.users'].with_user(self.bob), 'set_signalwire_call_state', ['idle'], {})
        personal.invalidate_recordset()
        group_caller.invalidate_recordset()
        self.assertEqual(personal.offer_user_id, self.bob)
        self.assertEqual(group_caller.state, 'queued')

    def test_nobody_jumps_the_line(self):
        first = self._waiting('CA-1')
        # Bob comes free without anyone noticing, then a second caller arrives:
        # the free agent goes to the caller who was there first.
        self.bob.write({'signalwire_call_state': 'idle', 'signalwire_call_state_at': fields.Datetime.now()})
        body = self._call('CA-2', caller='+15559990000')
        self.assertNotIn('<Sip', body)
        # The first caller went to Bob, so this one is now next in line.
        self.assertIn('You are next in line.', body)
        first.invalidate_recordset()
        self.assertEqual(first.offer_user_id, self.bob)
        self.redirect.assert_called_once_with(f'/signalwire/voice/queue_connect/{first.id}')

    def test_a_caller_cannot_be_handed_out_twice(self):
        call = self._waiting()
        call.write({'state': 'ringing', 'offer_user_id': self.jane.id})
        self.assertFalse(call._queue_try_offer())

    # ---- Situation 2: the receptionist ----

    def test_receptionist_adds_the_caller_to_a_personal_queue(self):
        call = self.env['signalwire.live_call'].create({
            'call_sid': 'CA-R', 'phone_number_id': self.number.id, 'from_number': '+15550002222'})
        call.action_add_to_queue(self.jane.id)
        self.assertEqual((call.state, call.queue_user_id), ('queued', self.jane))
        self.redirect.assert_called_once_with(f'/signalwire/voice/queue_wait/{call.id}')

    def test_direct_line_busy_means_their_personal_queue(self):
        self._busy(self.jane)
        body = self._call('CA-D', to='+12084449667')
        self.assertNotIn('<Sip', body)
        self.assertIn('/signalwire/voice/queue_choice/', body)
        self.assertEqual(self._live('CA-D').queue_user_id, self.jane)

    # ---- limits and the cron ----

    def test_longest_wait_sends_the_caller_to_voicemail(self):
        self.group.queue_max_wait_minutes = 5
        call = self._waiting()
        call.queued_at = fields.Datetime.now() - timedelta(minutes=6)
        self.env['signalwire.live_call']._cron_queue_tick()
        self.redirect.assert_called_with(f'/signalwire/voice/queue_timeout/{call.id}')
        body = self.url_open(f'/signalwire/voice/queue_timeout/{call.id}', data={
            'CallSid': 'CA-1', 'From': '+15551234567'}).text
        self.assertIn('<Record', body)

    def test_cron_offers_waiting_callers_when_someone_is_free(self):
        call = self._waiting()
        self.bob.write({'signalwire_call_state': 'idle', 'signalwire_call_state_at': fields.Datetime.now()})
        self.env['signalwire.live_call']._cron_queue_tick()
        call.invalidate_recordset()
        self.assertEqual(call.offer_user_id, self.bob)

    # ---- Situation 3: after hours ----

    def test_callback_when_we_open(self):
        menu = self.env['signalwire.ivr.menu'].create({'name': 'Night', 'greeting_text': 'We are closed.'})
        self.env['signalwire.ivr.menu.option'].create({
            'menu_id': menu.id, 'digit': '1', 'action_type': 'callback_open',
            'target_call_group_id': self.group.id})
        self.direct.calendar_id = self.env.ref('resource.resource_calendar_std')
        body = self.url_open(f'/signalwire/voice/ivr/{menu.id}/{self.direct.id}/digit', data={
            'Digits': '1', 'From': '+15551234567', 'CallSid': 'CA-N'}).text
        self.assertIn('when we open', body)
        request = self.env['signalwire.callback_request'].search([('phone_number', '=', '+15551234567')])
        opening = self.direct._signalwire_next_opening()
        self.assertLess(abs((request.not_before - opening).total_seconds()), 5)
        # Nobody is alerted before then...
        request.not_before = fields.Datetime.now() + timedelta(hours=8)
        self.assertFalse(request._users_to_alert())
        # ...and the free group members are, once it's time.
        request.not_before = fields.Datetime.now() - timedelta(minutes=1)
        self.env['signalwire.callback_request']._cron_alert_due_callbacks()
        self.env.cr.precommit.run()
        alerted = [json.loads(b.channel)[-1] for b in self.env['bus.bus'].sudo().search([])
                   if json.loads(b.message).get('type') == 'signalwire_callback/alert']
        self.assertIn(self.jane.partner_id.id, alerted)
        self.assertTrue(request.alerted_at)

    # ---- the panel ----

    def test_panel_lists_the_queues(self):
        receptionist = self.env['res.users'].create({
            'name': 'Rita', 'login': 'rita.q@example.com',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id, self.env.ref(
                'signalwire_voip_click2call.group_signalwire_receptionist').id])]})
        self._waiting('CA-1')
        self._call('CA-2', caller='+15559990000')
        data = call_kw(self.env['res.users'].with_user(receptionist),
                       'get_signalwire_receptionist_panel_data', [], {})
        (queue,) = data['queues']
        self.assertEqual(queue['name'], 'Sales')
        self.assertEqual(len(queue['callers']), 2)
        self.assertEqual(queue['free'], 0)
        positions = sorted(c['position'] for c in data['calls'] if c['state'] == 'queued')
        self.assertEqual(positions, [1, 2])
