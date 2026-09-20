# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSignalWireServerClick2Call(TransactionCase):

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

    def test_sip_domain_returns_the_configured_value(self):
        # SignalWire support confirmed (2026-09-20) the real SIP
        # domain carries a hidden per-space suffix that can't be
        # derived from the Space domain alone - it must be configured
        # directly rather than guessed.
        self.assertEqual(self.server._get_sip_domain(), 'example-abc123.sip.signalwire.com')

    def test_sip_domain_unset_raises_a_clear_error(self):
        self.server.sip_domain = False
        with self.assertRaises(UserError):
            self.server._get_sip_domain()

    def test_setup_click2call_creates_a_pbx_record(self):
        pbx = self.server.action_setup_click2call()

        self.assertEqual(pbx.name, 'Test SignalWire')
        self.assertEqual(pbx.domain, 'example-abc123.sip.signalwire.com')
        self.assertEqual(pbx.ws_server, 'wss://example-abc123.sip.signalwire.com')
        self.assertEqual(pbx.mode, 'prod')

    def test_setup_click2call_is_idempotent(self):
        first = self.server.action_setup_click2call()
        second = self.server.action_setup_click2call()

        self.assertEqual(first, second)
        self.assertEqual(
            self.env['voip.pbx'].search_count([('name', '=', 'Test SignalWire')]), 1)
