# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests.common import HttpCase, TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCustomerNumbersAreHandsOff(TransactionCase):
    """A customer's number is run from their own Odoo: Connect from here
    would point their calls at this Odoo."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        server = cls.env['signalwire.server'].create({
            'name': 'S', 'space': 'x.signalwire.com', 'sip_domain': 'x.sip.signalwire.com',
            'project_id': 'p', 'api_token': 't'})
        customer = cls.env['res.partner'].create({'name': 'TFL Conference'})
        sub = cls.env['signalwire.subproject'].create({
            'name': 'TFL', 'server_id': server.id, 'account_sid': 'sub-tfl', 'state': 'active',
            'partner_id': customer.id})
        cls.theirs = cls.env['signalwire.phone_number'].create({
            'name': '+17075898352', 'sid': 'pn-tfl', 'subproject_id': sub.id})
        cls.user = cls.env['res.users'].create({
            'name': 'Agent', 'login': 'agent.cust@example.com', 'voip_username': 'user_agent'})

    def test_connect_is_refused(self):
        with self.assertRaisesRegex(UserError, "TFL Conference's number"):
            self.theirs.action_configure_inbound_routing()

    def test_routing_cant_be_changed(self):
        with self.assertRaises(UserError):
            self.theirs.write({'route_type': 'user', 'assigned_user_id': self.user.id})


@tagged('post_install', '-at_install')
class TestNoPhoneGoesToVoicemail(HttpCase):

    def test_person_without_any_phone_gets_their_voicemail(self):
        server = self.env['signalwire.server'].create({
            'name': 'S', 'space': 'x.signalwire.com', 'sip_domain': 'x.sip.signalwire.com',
            'project_id': 'p', 'api_token': 't'})
        sub = self.env['signalwire.subproject'].create({
            'name': 'Ours', 'server_id': server.id, 'account_sid': 'p', 'state': 'active'})
        person = self.env['res.users'].create({'name': 'No Phone Yet', 'login': 'nophone@example.com'})
        self.env['signalwire.phone_number'].create({
            'name': '+12085550111', 'sid': 'pn-np', 'subproject_id': sub.id,
            'assigned_user_id': person.id})
        body = self.url_open('/signalwire/voice/inbound', data={
            'To': '+12085550111', 'From': '+15551234567', 'CallSid': 'CA-np'}).text
        self.assertIn(f'/signalwire/voice/voicemail_complete/{person.id}', body)
        self.assertNotIn("couldn't connect", body)
