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

    def test_search_numbers_returns_location_and_capabilities(self):
        client = self._mock_client()
        client.relay_get.return_value = {'data': [
            {'e164': '+17075550100', 'national_number_formatted': '(707) 555-0100',
             'rate_center': 'SANTA ROSA', 'region': 'CA', 'capabilities': ['voice', 'fax']},
            {'e164': '+17075550101', 'national_number_formatted': None},
        ]}

        numbers = self.server.search_numbers(
            match='ends_with', pattern='0100', area_code='707', region='ca', city='Santa Rosa')

        client.relay_get.assert_called_once_with(
            'phone_numbers/search', number_type='local', max_results=50, ends_with='0100',
            areacode='707', region='CA', city='Santa Rosa')
        self.assertEqual(numbers[0], {
            'e164': '+17075550100', 'national': '(707) 555-0100', 'region': 'CA',
            'rate_center': 'SANTA ROSA', 'capabilities': ['voice', 'fax']})
        self.assertEqual(numbers[1]['national'], '+17075550101')
        self.assertEqual(numbers[1]['capabilities'], [])

    def test_search_numbers_turns_letters_into_keypad_digits(self):
        client = self._mock_client()
        client.relay_get.return_value = {'data': []}
        self.server.search_numbers(number_type='toll_free', match='contains', pattern='Bear-1')
        client.relay_get.assert_called_once_with(
            'phone_numbers/search', number_type='tollfree', max_results=50, contains='23271')

    def test_search_numbers_refuses_bad_input_before_calling_signalwire(self):
        client = self._mock_client()
        for kwargs, message in [
            ({'pattern': '12'}, '3 to 7'),
            ({'pattern': '12345678'}, '3 to 7'),
            ({'pattern': '55*'}, 'only digits and letters'),
            ({'pattern': '555', 'match': 'sounds_like'}, 'starts with'),
            ({'area_code': '107'}, 'area code'),
            ({'city': 'Santa Rosa'}, 'state before a city'),
            ({'region': 'California'}, 'two-letter'),
            ({'number_type': 'toll_free', 'region': 'CA'}, "can't be searched"),
            ({'number_type': 'shortcode'}, 'Unknown number type'),
        ]:
            with self.assertRaisesRegex(UserError, message):
                self.server.search_numbers(**kwargs)
        client.relay_get.assert_not_called()

    def test_toll_free_search_retries_within_a_small_space_limit(self):
        from odoo.addons.signalwire_voip.models.signalwire_api import SignalWireAPIError
        client = self._mock_client()
        client.relay_get.side_effect = [SignalWireAPIError('max_results too high'),
                                        {'data': [{'e164': '+18885550100'}]}]
        numbers = self.server.search_numbers(number_type='toll_free')
        self.assertEqual([n['e164'] for n in numbers], ['+18885550100'])
        self.assertEqual(client.relay_get.call_args.kwargs['max_results'], 10)

    def test_local_search_errors_are_not_retried(self):
        from odoo.addons.signalwire_voip.models.signalwire_api import SignalWireAPIError
        client = self._mock_client()
        client.relay_get.side_effect = SignalWireAPIError('nope')
        with self.assertRaises(SignalWireAPIError):
            self.server.search_numbers()
        self.assertEqual(client.relay_get.call_count, 1)

    def test_search_available_numbers_handles_an_empty_result(self):
        self._mock_client({'available_phone_numbers': []})
        self.assertEqual(self.server.search_available_numbers('sub-sid', 'US'), [])
