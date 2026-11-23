# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestCallStatusController(HttpCase):
    """The number's status callback ends a live call the moment it's over,
    and an answered leg marks it Connected, to whoever picked up."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'sip_domain': 'example-abc123.sip.signalwire.com',
            'project_id': 'pid123', 'api_token': 'tok456',
        })
        cls.subproject = cls.env['signalwire.subproject'].create({
            'name': 'Internal Team', 'server_id': cls.server.id,
            'account_sid': 'sub-abc', 'state': 'active',
        })
        cls.user = cls.env['res.users'].create({
            'name': 'Jane Agent', 'login': 'jane.status@example.com',
            'voip_username': 'user_jane',
        })
        cls.number = cls.env['signalwire.phone_number'].create({
            'name': '+12084449665', 'sid': 'pn-123',
            'subproject_id': cls.subproject.id, 'assigned_user_id': cls.user.id,
        })

    def setUp(self):
        super().setUp()
        self.call = self.env['signalwire.live_call'].create({
            'call_sid': 'CA-parent', 'phone_number_id': self.number.id,
            'from_number': '+15551230000',
        })

    def test_finished_call_is_ended_at_once(self):
        for status in ('completed', 'canceled', 'no-answer', 'busy', 'failed'):
            with self.subTest(status=status):
                self.call.state = 'ringing'
                response = self.url_open('/signalwire/voice/status', data={
                    'CallSid': 'CA-parent', 'CallStatus': status})
                self.assertEqual(response.status_code, 204)
                self.call.invalidate_recordset()
                self.assertEqual(self.call.state, 'ended')

    def test_call_still_going_is_left_alone(self):
        self.url_open('/signalwire/voice/status', data={
            'CallSid': 'CA-parent', 'CallStatus': 'in-progress'})
        self.call.invalidate_recordset()
        self.assertEqual(self.call.state, 'ringing')

    def test_answered_leg_marks_the_call_connected_to_that_user(self):
        response = self.url_open(f'/signalwire/voice/leg_answered/{self.user.id}', data={
            'CallSid': 'CA-child', 'ParentCallSid': 'CA-parent',
            'CallStatus': 'in-progress'})
        self.assertEqual(response.status_code, 204)
        self.call.invalidate_recordset()
        self.assertEqual(self.call.state, 'connected')
        self.assertEqual(self.call.assigned_user_id, self.user)

    def test_ringing_legs_ask_to_report_their_answer(self):
        response = self.url_open('/signalwire/voice/inbound', data={
            'To': '+12084449665', 'From': '+15551230000', 'CallSid': 'CA-new'})
        self.assertIn('statusCallbackEvent="answered"', response.text)
        self.assertIn(f'/signalwire/voice/leg_answered/{self.user.id}', response.text)


@tagged('post_install', '-at_install')
class TestEffectiveCallState(HttpCase):

    def test_ringing_that_never_ended_shows_as_available(self):
        user = self.env['res.users'].create({
            'name': 'Stuck Ringer', 'login': 'stuck.ringer@example.com'})
        user.write({
            'signalwire_call_state': 'ringing',
            'signalwire_call_state_at': fields.Datetime.now() - timedelta(minutes=5)})
        self.assertEqual(user._signalwire_effective_call_state(), 'idle')
        user.signalwire_call_state_at = fields.Datetime.now()
        self.assertEqual(user._signalwire_effective_call_state(), 'ringing')
        user.signalwire_call_state = 'on_call'
        user.signalwire_call_state_at = fields.Datetime.now() - timedelta(hours=1)
        self.assertEqual(user._signalwire_effective_call_state(), 'on_call')
