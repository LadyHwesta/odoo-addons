# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSignalWirePhoneNumberClick2Call(TransactionCase):

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
        cls.subproject = cls.env['signalwire.subproject'].create({
            'name': 'Internal Team', 'server_id': cls.server.id,
            'account_sid': 'sub-abc', 'state': 'active',
        })
        cls.number = cls.env['signalwire.phone_number'].create({
            'name': '+12084449665', 'sid': 'pn-123',
            'subproject_id': cls.subproject.id,
        })
        cls.user = cls.env['res.users'].create({
            'name': 'Jane Agent', 'login': 'jane.agent@example.com',
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

    def test_configure_routing_requires_an_assigned_user(self):
        with self.assertRaises(UserError):
            self.number.action_configure_inbound_routing()

    def test_configure_routing_requires_a_provisioned_softphone(self):
        self.number.assigned_user_id = self.user
        with self.assertRaises(UserError):
            self.number.action_configure_inbound_routing()

    def test_configure_routing_sets_the_voice_url(self):
        self.user.write({'voip_username': f'user{self.user.id}'})
        self.number.assigned_user_id = self.user

        self.number.action_configure_inbound_routing()

        self.signalwire_client.compat_post.assert_called_once_with(
            'Accounts/sub-abc/IncomingPhoneNumbers/pn-123.json',
            VoiceUrl='https://odoo.example.com/signalwire/voice/inbound')
