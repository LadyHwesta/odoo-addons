# -*- coding: utf-8 -*-
import base64
import hashlib
import hmac
import time

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

    def test_generate_turn_credentials_returns_false_when_unconfigured(self):
        self.assertFalse(self.server._generate_turn_credentials())

    def test_generate_turn_credentials_computes_the_correct_hmac(self):
        self.server.write({'turn_host': '203.0.113.4:3478', 'turn_secret': 'sekrit'})

        result = self.server._generate_turn_credentials(ttl_seconds=3600)

        self.assertEqual(
            result['urls'],
            ['turn:203.0.113.4:3478?transport=udp', 'turn:203.0.113.4:3478?transport=tcp'])
        expiry = int(result['username'].split(':')[0])
        self.assertAlmostEqual(expiry, int(time.time()) + 3600, delta=5)
        expected_digest = hmac.new(
            b'sekrit', result['username'].encode(), hashlib.sha1).digest()
        self.assertEqual(result['credential'], base64.b64encode(expected_digest).decode())

    def test_generate_turn_credentials_requires_both_host_and_secret(self):
        self.server.turn_host = '203.0.113.4:3478'
        self.assertFalse(self.server._generate_turn_credentials())
