# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.tests.common import HttpCase, tagged

from odoo.addons.signalwire_voip_click2call.controllers.outbound import dialed_number, sip_user

CLIENT = 'odoo.addons.signalwire_voip.models.signalwire_server.SignalWireServer._get_client'


@tagged('post_install', '-at_install')
class TestOutboundViaOdoo(HttpCase):
    """Outside calls ask Odoo and go out as the right company's number."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.meskis = cls.env.company
        cls.meskis.name = 'Meskis Works'
        cls.dj = cls.env['res.company'].create({'name': 'DJ Em Bass'})
        cls.branch = cls.env['res.company'].create({'name': 'North Branch', 'parent_id': cls.meskis.id})
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test', 'space': 'example.signalwire.com', 'sip_domain': 'example-abc.sip.signalwire.com',
            'project_id': 'pid', 'api_token': 'tok'})
        sub = cls.env['signalwire.subproject'].create({
            'name': 'Ours', 'server_id': cls.server.id, 'account_sid': 'pid', 'state': 'active'})
        Number = cls.env['signalwire.phone_number']
        cls.meskis_number = Number.create({'name': '+17078021991', 'sid': 'pn-1', 'subproject_id': sub.id,
                                           'e911_status': 'active', 'company_id': cls.meskis.id})
        cls.dj_number = Number.create({'name': '+17075550199', 'sid': 'pn-2', 'subproject_id': sub.id,
                                       'company_id': cls.dj.id})
        cls.meskis.signalwire_main_number_id = cls.meskis_number
        cls.dj.signalwire_main_number_id = cls.dj_number
        cls.user = cls.env['res.users'].create({
            'name': 'Tiesa Test', 'login': 'tiesa.outbound@example.com', 'voip_username': 'tiesa.test9',
            'company_id': cls.meskis.id, 'company_ids': [(6, 0, [cls.meskis.id, cls.dj.id, cls.branch.id])],
            'signalwire_server_id': cls.server.id, 'signalwire_sip_endpoint_id': 'ep-1',
            'group_ids': [(4, cls.env.ref('base.group_user').id)]})
        with patch(CLIENT):
            cls.user.signalwire_outbound_number_id = cls.meskis_number
            cls.server.caller_id_by_company = True

    def _call(self, to, frm='sip:tiesa.test9@example-abc.sip.signalwire.com'):
        return self.url_open('/signalwire/voice/outbound', data={
            'CallSid': 'CA-1', 'From': frm, 'To': to, 'Direction': 'inbound'}).text

    def _note(self, number, record=None, company=None):
        env = self.env(user=self.user, context={'allowed_company_ids': [(company or self.meskis).id]
                                                + self.user.company_ids.ids})
        return env['res.users'].signalwire_note_outbound_call(
            number, record._name if record else False, record.id if record else False)

    # ---- reading the request ----

    def test_reading_the_dialed_number(self):
        self.assertEqual(sip_user('sip:tiesa.meskis2@x.sip.signalwire.com'), 'tiesa.meskis2')
        self.assertEqual(dialed_number('sip:3605810647@x.sip.signalwire.com'), '+13605810647')
        self.assertEqual(dialed_number('sip:+17075551234@x.sip.signalwire.com'), '+17075551234')
        self.assertEqual(dialed_number('+1 (707) 555-1234'), '+17075551234')
        self.assertEqual(dialed_number('sip:911@x.sip.signalwire.com'), '911')
        self.assertEqual(dialed_number('sip:jane.agent4@x.sip.signalwire.com'), '')

    # ---- choosing the number ----

    def test_the_record_clicked_decides(self):
        dj_record = self.env['res.partner'].create({'name': 'DJ client', 'company_id': self.dj.id})
        result = self._note('7075551234', record=dj_record)
        self.assertEqual(result['label'], 'Calling as DJ Em Bass (+17075550199)')
        self.assertIn('<Dial callerId="+17075550199"><Number>+17075551234</Number></Dial>',
                      self._call('sip:7075551234@example-abc.sip.signalwire.com'))

    def test_the_contacts_company_decides_hand_dialed_calls(self):
        self.env['res.partner'].create({'name': 'Wedding Couple', 'phone': '+1 707 555 4321',
                                        'company_id': self.dj.id})
        self.assertIn('callerId="+17075550199"', self._call('sip:7075554321@x'))

    def test_otherwise_the_current_company_and_a_branch_uses_its_parent(self):
        intent_label = self._note('7075550001', company=self.branch)['label']
        self.assertIn('+17078021991', intent_label)  # North Branch has no number: its parent's
        self.assertIn('callerId="+17078021991"', self._call('sip:7075550001@x'))
        self.assertIn('DJ Em Bass', self._note('7075550002', company=self.dj)['label'])

    def test_with_nothing_to_go_on_the_persons_own_company(self):
        self.assertIn('callerId="+17078021991"', self._call('sip:4155550000@x'))

    def test_911_always_uses_calls_out_as(self):
        dj_record = self.env['res.partner'].create({'name': 'DJ client', 'company_id': self.dj.id})
        self._note('911', record=dj_record)
        self.assertIn('<Dial callerId="+17078021991"><Number>911</Number></Dial>', self._call('sip:911@x'))

    def test_no_e911_no_outside_calls(self):
        self.meskis_number.e911_status = 'none'
        xml = self._call('sip:7075551234@x')
        self.assertIn('<Hangup/>', xml)
        self.assertNotIn('<Number>', xml)

    def test_unknown_phones_are_refused(self):
        self.assertIn('<Reject/>', self._call('sip:7075551234@x', frm='sip:stranger@x'))

    def test_calls_to_other_phones_still_ring_them(self):
        xml = self._call('sip:jane.agent4@example-abc.sip.signalwire.com')
        self.assertIn('<Sip>sip:jane.agent4@example-abc.sip.signalwire.com</Sip>', xml)

    def test_switched_off_nothing_changes(self):
        with patch(CLIENT):
            self.server.caller_id_by_company = False
        self.assertEqual(self._note('7075551234'), {})

    # ---- the switch ----

    def test_the_switch_moves_every_phone(self):
        client = MagicMock()
        with patch(CLIENT, return_value=client):
            self.server.caller_id_by_company = False
            self.assertEqual(client.relay_put.call_args.kwargs['call_handler'], 'passthrough')
            self.server.caller_id_by_company = True
            kwargs = client.relay_put.call_args.kwargs
            self.assertEqual(client.relay_put.call_args.args[0], 'endpoints/sip/ep-1')
            self.assertEqual(kwargs['call_handler'], 'laml_webhooks')
            self.assertTrue(kwargs['call_request_url'].endswith('/signalwire/voice/outbound'))
            self.assertEqual(kwargs['send_as'], '+17078021991')

    def test_phones_are_set_up_in_their_companys_account(self):
        other = self.env['signalwire.server'].create({
            'name': 'DJ account', 'space': 'dj.signalwire.com', 'project_id': 'p2', 'api_token': 't2',
            'company_id': self.dj.id})
        Server = self.env['signalwire.server']
        self.assertEqual(Server._for_company(self.dj), other)
        self.assertEqual(Server._for_company(self.branch), self.server)

    def test_a_branch_can_pick_its_parents_numbers(self):
        customer = self.env['res.partner'].create({'name': 'TFL Conference'})
        their_sub = self.env['signalwire.subproject'].create({
            'name': 'TFL', 'server_id': self.server.id, 'account_sid': 'sub-tfl', 'state': 'active',
            'partner_id': customer.id})
        theirs = self.env['signalwire.phone_number'].create({
            'name': '+17075898352', 'sid': 'pn-tfl', 'subproject_id': their_sub.id})
        domain = self.env['res.company']._fields['signalwire_main_number_id'].domain
        allowed = self.env['signalwire.phone_number'].search(
            eval(domain, {'id': self.branch.id}))
        self.assertIn(self.meskis_number, allowed)
        self.assertNotIn(self.dj_number, allowed)  # another company's
        self.assertNotIn(theirs, allowed)  # a customer's
