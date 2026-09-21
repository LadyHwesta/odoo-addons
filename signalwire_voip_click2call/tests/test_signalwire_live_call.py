# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSignalWireLiveCall(TransactionCase):

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
        cls.number = cls.env['signalwire.phone_number'].create({
            'name': '+12084449665', 'sid': 'pn-123', 'subproject_id': cls.subproject.id,
        })
        cls.user = cls.env['res.users'].create({
            'name': 'Jane Agent', 'login': 'jane.agent2@example.com',
            'voip_username': 'user_jane',
        })

    def setUp(self):
        super().setUp()
        self.signalwire_client = MagicMock()
        patcher = patch(
            'odoo.addons.signalwire_voip.models.signalwire_server.'
            'SignalWireServer._get_client', return_value=self.signalwire_client)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.env['ir.config_parameter'].sudo().set_param(
            'web.base.url', 'https://odoo.example.com')

    def _call(self, **extra):
        vals = {
            'call_sid': 'CA123', 'phone_number_id': self.number.id,
            'from_number': '+15551234567',
        }
        vals.update(extra)
        return self.env['signalwire.live_call'].create(vals)

    def test_create_defaults_to_ringing(self):
        call = self._call()
        self.assertEqual(call.state, 'ringing')

    def test_route_to_user_requires_a_provisioned_softphone(self):
        call = self._call()
        no_phone_user = self.env['res.users'].create({
            'name': 'No Phone', 'login': 'no.phone2@example.com'})
        with self.assertRaises(UserError):
            call.action_route_to_user(no_phone_user.id)

    def test_route_to_user_redirects_and_updates_state(self):
        call = self._call()

        call.action_route_to_user(self.user.id)

        self.signalwire_client.compat_post.assert_called_once()
        args, kwargs = self.signalwire_client.compat_post.call_args
        self.assertEqual(args[0], 'Accounts/sub-abc/Calls/CA123.json')
        self.assertIn(
            f'/signalwire/voice/route_to_user/{self.user.id}/{self.number.id}',
            kwargs['Url'])
        self.assertEqual(call.assigned_user_id, self.user)
        self.assertEqual(call.state, 'ringing')

    def test_park_redirects_to_the_hold_loop_and_updates_state(self):
        call = self._call()

        call.action_park()

        args, kwargs = self.signalwire_client.compat_post.call_args
        self.assertIn(f'/signalwire/voice/hold_loop/{self.number.id}', kwargs['Url'])
        self.assertEqual(call.state, 'parked')

    def test_send_to_voicemail_redirects_and_updates_state(self):
        call = self._call()

        call.action_send_to_voicemail(self.user.id)

        args, kwargs = self.signalwire_client.compat_post.call_args
        self.assertIn(
            f'/signalwire/voice/route_to_voicemail/{self.user.id}/{self.number.id}',
            kwargs['Url'])
        self.assertEqual(call.assigned_user_id, self.user)
