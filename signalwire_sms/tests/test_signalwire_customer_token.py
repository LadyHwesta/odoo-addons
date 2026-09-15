# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSignalWireCustomerToken(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'project_id': 'pid123', 'api_token': 'tok456',
        })
        cls.subproject = cls.env['signalwire.subproject'].create({
            'name': 'Customer Subproject', 'server_id': cls.server.id,
            'account_sid': 'sub-abc', 'state': 'active',
        })
        cls.token = cls.env['signalwire.customer.token'].create({
            'subproject_id': cls.subproject.id,
            'signalwire_token_id': 'tok-1', 'token': 'swapi_realsecret',
        })

    def setUp(self):
        super().setUp()
        self.signalwire_client = MagicMock()
        patcher = patch(
            'odoo.addons.signalwire_voip.models.signalwire_server.'
            'SignalWireServer._get_client', return_value=self.signalwire_client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_revoke_calls_the_delete_endpoint(self):
        self.token.action_revoke()

        self.signalwire_client.project_delete.assert_called_once_with(
            'project/tokens/tok-1')

    def test_revoke_deactivates_the_record(self):
        self.token.action_revoke()
        self.assertFalse(self.token.active)
