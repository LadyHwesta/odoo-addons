# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSignalWireDeskPhone(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'sip_domain': 'example-abc123.sip.signalwire.com',
            'project_id': 'pid123', 'api_token': 'tok456',
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

    def _phone(self, **overrides):
        vals = {
            'user_id': self.user.id, 'name': 'Front Desk',
            'mac_address': 'aa:bb:cc:dd:ee:ff', 'brand': 'yealink',
        }
        vals.update(overrides)
        return self.env['signalwire.desk_phone'].create(vals)

    def test_mac_address_is_normalized_on_create(self):
        phone = self._phone(mac_address='AA-BB-CC-DD-EE-FF')
        self.assertEqual(phone.mac_address, 'aabbccddeeff')

    def test_mac_address_is_normalized_on_write(self):
        phone = self._phone()
        phone.mac_address = '11:22:33:44:55:66'
        self.assertEqual(phone.mac_address, '112233445566')

    def test_invalid_mac_address_raises(self):
        with self.assertRaises(ValidationError):
            self._phone(mac_address='not-a-mac')

    def test_duplicate_mac_address_raises(self):
        self._phone(mac_address='aa:bb:cc:dd:ee:ff')
        with self.assertRaises(Exception):
            self._phone(mac_address='aabbccddeeff', name='Another Phone')

    def test_provision_creates_a_sip_endpoint(self):
        phone = self._phone()
        self.signalwire_client.relay_post.return_value = {
            'id': 'ep-desk-1', 'username': f'deskphone{phone.id}',
        }

        phone.action_provision()

        self.signalwire_client.relay_post.assert_called_once()
        args, kwargs = self.signalwire_client.relay_post.call_args
        self.assertEqual(args[0], 'endpoints/sip')
        self.assertEqual(kwargs['username'], f'deskphone{phone.id}')
        self.assertEqual(phone.signalwire_sip_endpoint_id, 'ep-desk-1')
        self.assertEqual(phone.voip_username, f'deskphone{phone.id}')
        self.assertTrue(phone.voip_password)

    def test_provision_twice_raises(self):
        phone = self._phone()
        self.signalwire_client.relay_post.return_value = {
            'id': 'ep-desk-1', 'username': f'deskphone{phone.id}',
        }
        phone.action_provision()

        with self.assertRaises(UserError):
            phone.action_provision()

    def test_release_calls_the_delete_endpoint_and_clears_fields(self):
        phone = self._phone()
        self.signalwire_client.relay_post.return_value = {
            'id': 'ep-desk-1', 'username': f'deskphone{phone.id}',
        }
        phone.action_provision()

        phone.action_release()

        self.signalwire_client.relay_delete.assert_called_once_with('endpoints/sip/ep-desk-1')
        self.assertFalse(phone.signalwire_sip_endpoint_id)
        self.assertFalse(phone.voip_username)
        self.assertFalse(phone.voip_password)

    def test_release_without_provisioning_raises(self):
        phone = self._phone()
        with self.assertRaises(UserError):
            phone.action_release()

    def test_provisioning_url_blank_until_provisioned(self):
        phone = self._phone()
        self.assertFalse(phone.provisioning_url)

    def test_provisioning_url_matches_yealink_pattern(self):
        phone = self._phone(brand='yealink', mac_address='aabbccddeeff')
        self.signalwire_client.relay_post.return_value = {
            'id': 'ep-desk-1', 'username': f'deskphone{phone.id}',
        }
        phone.action_provision()

        self.assertIn('/signalwire/provisioning/aabbccddeeff.cfg', phone.provisioning_url)

    def test_provisioning_url_matches_grandstream_pattern(self):
        phone = self._phone(brand='grandstream', mac_address='aabbccddeeff')
        self.signalwire_client.relay_post.return_value = {
            'id': 'ep-desk-1', 'username': f'deskphone{phone.id}',
        }
        phone.action_provision()

        self.assertIn('/signalwire/provisioning/cfgaabbccddeeff.xml', phone.provisioning_url)
