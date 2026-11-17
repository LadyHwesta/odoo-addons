# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.tests.common import HttpCase, tagged

from odoo.addons.signalwire_voip_click2call.controllers.outbound import dialed_number, sip_user


@tagged('post_install', '-at_install')
class TestOutboundViaOdoo(HttpCase):
    """The live test route: a softphone dialing out asks Odoo, and the call
    goes out exactly as it would directly (Calls Out As, E911 rule)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        server = cls.env['signalwire.server'].create({
            'name': 'Test', 'space': 'example.signalwire.com', 'sip_domain': 'example-abc.sip.signalwire.com',
            'project_id': 'pid', 'api_token': 'tok'})
        sub = cls.env['signalwire.subproject'].create({
            'name': 'Ours', 'server_id': server.id, 'account_sid': 'pid', 'state': 'active'})
        cls.number = cls.env['signalwire.phone_number'].create({
            'name': '+17078021991', 'sid': 'pn-1', 'subproject_id': sub.id, 'e911_status': 'active'})
        cls.user = cls.env['res.users'].create({
            'name': 'Tiesa Test', 'login': 'tiesa.outbound@example.com', 'voip_username': 'tiesa.test9',
            'signalwire_server_id': server.id, 'signalwire_sip_endpoint_id': 'ep-1'})
        with patch('odoo.addons.signalwire_voip.models.signalwire_server.SignalWireServer._get_client'):
            cls.user.signalwire_outbound_number_id = cls.number

    def _call(self, to, frm='sip:tiesa.test9@example-abc.sip.signalwire.com'):
        return self.url_open('/signalwire/voice/outbound', data={
            'CallSid': 'CA-1', 'From': frm, 'To': to, 'Direction': 'inbound'}).text

    def test_reading_the_dialed_number(self):
        self.assertEqual(sip_user('sip:tiesa.meskis2@x.sip.signalwire.com'), 'tiesa.meskis2')
        self.assertEqual(dialed_number('sip:7075551234@x.sip.signalwire.com'), '+17075551234')
        self.assertEqual(dialed_number('sip:+17075551234@x.sip.signalwire.com'), '+17075551234')
        self.assertEqual(dialed_number('+1 (707) 555-1234'), '+17075551234')
        self.assertEqual(dialed_number('sip:911@x.sip.signalwire.com'), '911')
        self.assertEqual(dialed_number('sip:jane.agent4@x.sip.signalwire.com'), '')

    def test_outside_call_goes_out_as_calls_out_as(self):
        xml = self._call('sip:7075551234@example-abc.sip.signalwire.com')
        self.assertIn('<Dial callerId="+17078021991"><Number>+17075551234</Number></Dial>', xml)

    def test_911_uses_the_e911_number(self):
        self.assertIn('<Dial callerId="+17078021991"><Number>911</Number></Dial>', self._call('sip:911@x'))

    def test_no_e911_no_outside_calls(self):
        self.number.e911_status = 'none'
        xml = self._call('sip:7075551234@x')
        self.assertIn('<Hangup/>', xml)
        self.assertNotIn('<Number>', xml)

    def test_unknown_phones_are_refused(self):
        self.assertIn('<Reject/>', self._call('sip:7075551234@x', frm='sip:stranger@x'))

    def test_calls_to_other_phones_still_ring_them(self):
        xml = self._call('sip:jane.agent4@example-abc.sip.signalwire.com')
        self.assertIn('<Sip>sip:jane.agent4@example-abc.sip.signalwire.com</Sip>', xml)

    def test_switch_and_switch_back(self):
        client = MagicMock()
        with patch('odoo.addons.signalwire_voip.models.signalwire_server.SignalWireServer._get_client',
                   return_value=client):
            self.user.action_signalwire_outbound_via_odoo()
            path, kwargs = client.relay_put.call_args.args[0], client.relay_put.call_args.kwargs
            self.assertEqual(path, 'endpoints/sip/ep-1')
            self.assertEqual(kwargs['call_handler'], 'laml_webhooks')
            self.assertTrue(kwargs['call_request_url'].endswith('/signalwire/voice/outbound'))
            self.user.action_signalwire_outbound_direct()
            self.assertEqual(client.relay_put.call_args.kwargs,
                             {'call_handler': 'passthrough', 'send_as': '+17078021991'})
