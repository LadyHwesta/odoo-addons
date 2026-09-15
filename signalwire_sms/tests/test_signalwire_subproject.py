# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSignalWireSubprojectSms(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'project_id': 'pid123', 'api_token': 'tok456',
        })

    def setUp(self):
        super().setUp()
        self.signalwire_client = MagicMock()
        patcher = patch(
            'odoo.addons.signalwire_voip.models.signalwire_server.'
            'SignalWireServer._get_client', return_value=self.signalwire_client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _subproject(self, provisioned=True):
        vals = {'name': 'Customer Subproject', 'server_id': self.server.id}
        if provisioned:
            vals.update({'account_sid': 'sub-abc', 'state': 'active'})
        return self.env['signalwire.subproject'].create(vals)

    def test_issue_token_calls_the_project_tokens_endpoint(self):
        self.signalwire_client.project_post.return_value = {
            'id': 'tok-1', 'token': 'swapi_realsecret',
        }
        subproject = self._subproject()

        subproject.action_issue_customer_token()

        self.signalwire_client.project_post.assert_called_once_with(
            'project/tokens', name='Customer Subproject - Customer Access',
            permissions=['messaging', 'numbers'], subproject_id='sub-abc')

    def test_issue_token_creates_a_customer_token_record(self):
        self.signalwire_client.project_post.return_value = {
            'id': 'tok-1', 'token': 'swapi_realsecret',
        }
        subproject = self._subproject()

        token = subproject.action_issue_customer_token()

        self.assertEqual(token.signalwire_token_id, 'tok-1')
        self.assertEqual(token.token, 'swapi_realsecret')
        self.assertEqual(token.subproject_id, subproject)

    def test_issue_token_requires_provisioning_first(self):
        subproject = self._subproject(provisioned=False)
        with self.assertRaises(UserError):
            subproject.action_issue_customer_token()
