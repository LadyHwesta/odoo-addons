# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.service.model import call_kw
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestReceptionistPanelData(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        server = cls.env['signalwire.server'].create({
            'name': 'S', 'space': 'x.signalwire.com', 'sip_domain': 'x.sip.signalwire.com',
            'project_id': 'p', 'api_token': 't'})
        sub = cls.env['signalwire.subproject'].create({
            'name': 'Sub', 'server_id': server.id, 'account_sid': 'sub-x', 'state': 'active'})
        cls.number = cls.env['signalwire.phone_number'].create({
            'name': '+12085550001', 'sid': 'pn-1', 'subproject_id': sub.id})
        groups = [cls.env.ref('base.group_user').id]
        cls.receptionist = cls.env['res.users'].create({
            'name': 'Rita Reception', 'login': 'rita.panel@example.com', 'voip_username': 'user_rita',
            'tz': 'America/Los_Angeles',
            'group_ids': [(6, 0, groups + [
                cls.env.ref('signalwire_voip_click2call.group_signalwire_receptionist').id])]})
        cls.sam = cls.env['res.users'].create({
            'name': 'Sam Staff', 'login': 'sam.panel@example.com', 'voip_username': 'user_sam',
            'group_ids': [(6, 0, groups)]})
        cls.plain = cls.env['res.users'].create({
            'name': 'Plain User', 'login': 'plain.panel@example.com',
            'group_ids': [(6, 0, groups)]})
        cls.customer = cls.env['res.partner'].create({
            'name': 'Carla Customer', 'phone': '+15551234567'})

    def _data(self):
        return call_kw(self.env['res.users'].with_user(self.receptionist),
                       'get_signalwire_receptionist_panel_data', [], {})

    def test_only_receptionists_get_it(self):
        with self.assertRaises(UserError):
            call_kw(self.env['res.users'].with_user(self.plain),
                    'get_signalwire_receptionist_panel_data', [], {})

    def test_caller_is_matched_to_their_appointment(self):
        now = fields.Datetime.now()
        event = self.env['calendar.event'].create({
            'name': 'Consultation', 'start': now + timedelta(minutes=30),
            'stop': now + timedelta(minutes=90),
            'partner_ids': [(6, 0, [self.sam.partner_id.id, self.customer.id])]})
        self.env['signalwire.live_call'].create({
            'call_sid': 'CA-1', 'phone_number_id': self.number.id, 'from_number': '+15551234567'})
        data = self._data()
        call = data['calls'][0]
        self.assertEqual(call['caller'], 'Carla Customer')
        self.assertEqual(call['events'][0]['id'], event.id)
        self.assertEqual(call['events'][0]['with'], 'Sam Staff')
        agenda = {e['id']: e for e in data['agenda']}
        self.assertTrue(agenda[event.id]['highlight'])
        sam = next(m for m in data['team'] if m['id'] == self.sam.id)
        self.assertEqual(sam['next']['name'], 'Consultation')
        self.assertFalse(sam['now'])  # nothing on now: False, not an empty list

    def test_status_combines_presence_and_calls(self):
        self.sam.write({'signalwire_presence': 'away'})
        self.assertEqual(self.sam._signalwire_panel_status(), 'away')
        self.sam.write({'signalwire_presence': 'mobile'})
        self.assertEqual(self.sam._signalwire_panel_status(), 'mobile')
        self.sam.write({'signalwire_call_state': 'on_call',
                        'signalwire_call_state_at': fields.Datetime.now()})
        self.assertEqual(self.sam._signalwire_panel_status(), 'on_call')

    def test_private_events_show_as_busy(self):
        now = fields.Datetime.now()
        self.env['calendar.event'].create({
            'name': 'Doctor', 'privacy': 'private', 'user_id': self.sam.id,
            'start': now - timedelta(minutes=10), 'stop': now + timedelta(minutes=50),
            'partner_ids': [(6, 0, [self.sam.partner_id.id])]})
        data = self._data()
        sam = next(m for m in data['team'] if m['id'] == self.sam.id)
        self.assertEqual(sam['now']['name'], 'Busy')
        self.assertNotIn('Doctor', [e['name'] for e in data['agenda']])
