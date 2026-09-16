# -*- coding: utf-8 -*-
from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestDeskPhoneProvisioningController(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'project_id': 'pid123', 'api_token': 'tok456',
        })
        cls.user = cls.env['res.users'].create({
            'name': 'Jane Agent', 'login': 'jane.agent@example.com',
        })

    def _provisioned_phone(self, brand, mac_address):
        phone = self.env['signalwire.desk_phone'].create({
            'user_id': self.user.id, 'name': 'Front Desk',
            'mac_address': mac_address, 'brand': brand,
        })
        phone.write({
            'signalwire_sip_endpoint_id': 'ep-desk-1',
            'signalwire_server_id': self.server.id,
            'voip_username': 'deskphoneXYZ',
            'voip_password': 'super-secret-pw',
        })
        return phone

    def test_yealink_filename_returns_a_matching_cfg(self):
        self._provisioned_phone('yealink', 'aabbccddeeff')

        response = self.url_open('/signalwire/provisioning/aabbccddeeff.cfg')

        self.assertEqual(response.status_code, 200)
        self.assertIn('account.1.user_name = deskphoneXYZ', response.text)
        self.assertIn('account.1.password = super-secret-pw', response.text)
        self.assertIn('account.1.sip_server.1.address = example.sip.signalwire.com',
                       response.text)

    def test_grandstream_filename_returns_a_matching_xml(self):
        self._provisioned_phone('grandstream', 'aabbccddeeff')

        response = self.url_open('/signalwire/provisioning/cfgaabbccddeeff.xml')

        self.assertEqual(response.status_code, 200)
        self.assertIn('<P35>deskphoneXYZ</P35>', response.text)
        self.assertIn('<P34>super-secret-pw</P34>', response.text)
        self.assertIn('<P47>example.sip.signalwire.com</P47>', response.text)

    def test_mac_lookup_is_normalized_regardless_of_how_it_was_saved(self):
        self._provisioned_phone('yealink', 'AA:BB:CC:DD:EE:FF')

        response = self.url_open('/signalwire/provisioning/aabbccddeeff.cfg')

        self.assertEqual(response.status_code, 200)
        self.assertIn('deskphoneXYZ', response.text)

    def test_unknown_mac_returns_404(self):
        response = self.url_open('/signalwire/provisioning/000000000000.cfg')
        self.assertEqual(response.status_code, 404)

    def test_unprovisioned_phone_returns_404(self):
        self.env['signalwire.desk_phone'].create({
            'user_id': self.user.id, 'name': 'Front Desk',
            'mac_address': 'aabbccddeeff', 'brand': 'yealink',
        })

        response = self.url_open('/signalwire/provisioning/aabbccddeeff.cfg')

        self.assertEqual(response.status_code, 404)

    def test_malformed_filename_returns_404(self):
        response = self.url_open('/signalwire/provisioning/not-a-real-filename')
        self.assertEqual(response.status_code, 404)
