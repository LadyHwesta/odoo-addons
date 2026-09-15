# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSignalWireServerClick2Call(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test SignalWire',
            'space': 'example.signalwire.com',
            'project_id': 'pid123',
            'api_token': 'tok456',
        })

    def test_sip_domain_uses_the_dot_sip_dot_host(self):
        # Confirmed live 2026-09-15 - the bare space domain serves the
        # dashboard and refuses a WebSocket upgrade; the real SIP/WSS
        # host has ".sip." inserted before ".signalwire.com".
        self.assertEqual(self.server._get_sip_domain(), 'example.sip.signalwire.com')

    def test_setup_click2call_creates_a_pbx_record(self):
        pbx = self.server.action_setup_click2call()

        self.assertEqual(pbx.name, 'Test SignalWire')
        self.assertEqual(pbx.domain, 'example.sip.signalwire.com')
        self.assertEqual(pbx.ws_server, 'wss://example.sip.signalwire.com')
        self.assertEqual(pbx.mode, 'prod')

    def test_setup_click2call_is_idempotent(self):
        first = self.server.action_setup_click2call()
        second = self.server.action_setup_click2call()

        self.assertEqual(first, second)
        self.assertEqual(
            self.env['voip.pbx'].search_count([('name', '=', 'Test SignalWire')]), 1)
