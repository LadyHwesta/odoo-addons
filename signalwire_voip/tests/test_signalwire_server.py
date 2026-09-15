# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSignalWireServer(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test SignalWire',
            'space': 'example.signalwire.com',
            'project_id': 'pid123',
            'api_token': 'tok456',
        })

    def _mock_client(self, compat_get_return_value=None):
        mock_client = MagicMock()
        if compat_get_return_value is not None:
            mock_client.compat_get.return_value = compat_get_return_value
        patcher = patch(
            'odoo.addons.signalwire_voip.models.signalwire_server.'
            'SignalWireServer._get_client', return_value=mock_client)
        patcher.start()
        self.addCleanup(patcher.stop)
        return mock_client

    def test_test_connection_reports_the_project_status(self):
        self._mock_client({'status': 'active'})
        with self.assertRaises(UserError) as cm:
            self.server.action_test_connection()
        self.assertIn('active', str(cm.exception))

    def test_search_available_numbers_returns_plain_e164_list(self):
        client = self._mock_client({'available_phone_numbers': [
            {'phone_number': '+14155550100'},
            {'phone_number': '+14155550101'},
        ]})

        numbers = self.server.search_available_numbers('sub-sid', 'US', area_code='415')

        self.assertEqual(numbers, ['+14155550100', '+14155550101'])
        client.compat_get.assert_called_once_with(
            'Accounts/sub-sid/AvailablePhoneNumbers/US/Local.json', AreaCode='415')

    def test_search_available_numbers_without_area_code_omits_the_param(self):
        client = self._mock_client({'available_phone_numbers': []})

        self.server.search_available_numbers('sub-sid', 'US')

        client.compat_get.assert_called_once_with(
            'Accounts/sub-sid/AvailablePhoneNumbers/US/Local.json')

    def test_search_available_numbers_handles_an_empty_result(self):
        self._mock_client({'available_phone_numbers': []})
        self.assertEqual(self.server.search_available_numbers('sub-sid', 'US'), [])
