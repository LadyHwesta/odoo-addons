# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSignalWirePhoneNumber(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test SignalWire',
            'space': 'example.signalwire.com',
            'project_id': 'pid123',
            'api_token': 'tok456',
        })
        cls.subproject = cls.env['signalwire.subproject'].create({
            'name': 'Test Subproject',
            'server_id': cls.server.id,
            'account_sid': 'sub-abc',
            'state': 'active',
        })
        cls.number = cls.env['signalwire.phone_number'].create({
            'name': '+14155550100',
            'sid': 'pn-123',
            'subproject_id': cls.subproject.id,
        })

    def setUp(self):
        super().setUp()
        self.signalwire_client = MagicMock()
        patcher = patch(
            'odoo.addons.signalwire_voip.models.signalwire_server.'
            'SignalWireServer._get_client', return_value=self.signalwire_client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_release_calls_the_delete_endpoint(self):
        self.number.action_release()

        self.signalwire_client.compat_delete.assert_called_once_with(
            'Accounts/sub-abc/IncomingPhoneNumbers/pn-123.json')

    def test_release_deactivates_the_record(self):
        self.number.action_release()
        self.assertFalse(self.number.active)
