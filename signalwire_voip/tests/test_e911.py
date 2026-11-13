# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.signalwire_voip.models.signalwire_api import SignalWireAPIError


@tagged('post_install', '-at_install')
class TestE911(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test', 'space': 'example.signalwire.com',
            'project_id': 'pid123', 'api_token': 'tok456',
        })
        cls.subproject = cls.env['signalwire.subproject'].create({
            'name': 'Sub', 'server_id': cls.server.id, 'account_sid': 'pid123', 'state': 'active'})
        cls.number = cls.env['signalwire.phone_number'].create({
            'name': '+17075550100', 'sid': 'pn-123', 'subproject_id': cls.subproject.id})
        cls.ca = cls.env['res.country.state'].search(
            [('country_id.code', '=', 'US'), ('code', '=', 'CA')], limit=1)

    def setUp(self):
        super().setUp()
        self.client = MagicMock()
        patcher = patch(
            'odoo.addons.signalwire_voip.models.signalwire_server.'
            'SignalWireServer._get_client', return_value=self.client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _address(self, **vals):
        return self.env['signalwire.e911.address'].create(dict({
            'name': 'TFL Conference', 'server_id': self.server.id,
            'first_name': 'Front', 'last_name': 'Desk',
            'street_number': '1275', 'street_name': '4th St', 'unit_type': 'Suite',
            'unit_number': '5039', 'city': 'Santa Rosa', 'state_id': self.ca.id, 'zip': '95404',
        }, **vals))

    def _registered(self):
        address = self._address()
        self.client.relay_post.return_value = {'id': 'addr-1', 'emergency_enabled': True}
        address.action_register()
        return address

    # -- addresses ----------------------------------------------------------

    def test_register_sends_a_911_enabled_us_address(self):
        address = self._registered()
        path, = self.client.relay_post.call_args.args
        body = self.client.relay_post.call_args.kwargs
        self.assertEqual(path, 'addresses')
        self.assertTrue(body['emergency_enabled'])
        self.assertEqual(body['country'], 'US')
        self.assertEqual(body['state'], 'CA')
        self.assertEqual(body['postal_code'], '95404')
        self.assertEqual(body['address_type'], 'Suite')
        self.assertEqual(body['address_number'], '5039')
        self.assertEqual(address.state, 'registered')
        self.assertEqual(address.remote_id, 'addr-1')

    def test_rejected_address_keeps_the_carriers_suggestions(self):
        address = self._address(street_name='4th Strt')
        self.client.relay_post.side_effect = SignalWireAPIError('Address not found', payload={
            'errors': [{'detail': 'Address not found'}],
            'candidates': [{'street_number': '1275', 'street_name': '4th St',
                            'city': 'Santa Rosa', 'state': 'CA', 'postal_code': '95404'}]})
        with self.assertRaisesRegex(UserError, '1275 4th St'):
            address.action_register()
        self.assertEqual(address.state, 'rejected')
        self.assertIn('1275 4th St', address.suggestions)

    def test_registered_address_cant_be_edited(self):
        address = self._registered()
        with self.assertRaises(UserError):
            address.zip = '95401'

    def test_dispatcher_name_is_at_most_32_characters(self):
        with self.assertRaises(ValidationError):
            self._address(name='x' * 33)

    # -- numbers -------------------------------------------------------------

    def test_assign_starts_pending(self):
        address = self._registered()
        self.number.e911_address_id = address
        self.client.relay_post.return_value = {'id': 'pn-123', 'e911_status': 'pending'}
        self.number.action_assign_e911()
        self.assertEqual(self.client.relay_post.call_args.args[0], 'phone_numbers/pn-123/e911_address')
        self.assertEqual(self.client.relay_post.call_args.kwargs, {'e911_address_id': 'addr-1'})
        self.assertEqual(self.number.e911_status, 'pending')
        self.assertFalse(self.number.e911_active)

    def test_assign_needs_a_registered_address(self):
        self.number.e911_address_id = self._address()
        with self.assertRaisesRegex(UserError, 'Register'):
            self.number.action_assign_e911()

    def test_check_status_and_the_cron_activate_it(self):
        self.number.e911_status = 'pending'
        self.client.relay_get.return_value = {'id': 'pn-123', 'e911_status': 'active'}
        with patch.object(type(self.number), '_on_e911_status_changed') as hook:
            self.env['signalwire.phone_number']._cron_refresh_e911()
        self.assertEqual(self.client.relay_get.call_args.args[0], 'phone_numbers/pn-123')
        self.assertEqual(self.number.e911_status, 'active')
        self.assertTrue(self.number.e911_active)
        hook.assert_called_once()

    def test_cron_skips_numbers_that_arent_pending(self):
        self.number.e911_status = 'active'
        self.env['signalwire.phone_number']._cron_refresh_e911()
        self.client.relay_get.assert_not_called()

    def test_remove(self):
        self.number.e911_status = 'active'
        self.number.action_remove_e911()
        self.assertEqual(self.client.relay_delete.call_args.args[0], 'phone_numbers/pn-123/e911_address')
        self.assertEqual(self.number.e911_status, 'pending_removal')

    def test_unknown_status_is_treated_as_none(self):
        self.number._e911_apply({'e911_status': 'something-new'})
        self.assertEqual(self.number.e911_status, 'none')

    def test_numbers_are_ours_or_a_customers(self):
        self.assertEqual(self.number.number_use, 'own')
        self.subproject.partner_id = self.env.company.partner_id
        self.assertEqual(self.number.number_use, 'own')
        self.subproject.partner_id = self.env['res.partner'].create({'name': 'Customer'})
        self.assertEqual(self.number.number_use, 'customer')

    def test_dashboard_counts_numbers_without_e911(self):
        data = self.env['signalwire.dashboard'].get_dashboard_data()
        tile = next(t for t in data['tiles'] if t['key'] == 'e911')
        self.assertGreaterEqual(tile['value'], 1)
        self.assertEqual(tile['tone'], 'warning')
