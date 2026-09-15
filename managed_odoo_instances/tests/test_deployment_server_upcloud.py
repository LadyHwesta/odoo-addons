# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDeploymentServerUpCloud(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account = cls.env['upcloud.account'].create({
            'name': 'Test UpCloud Account', 'api_token': 'ucat_test',
            'ssh_public_key': 'ssh-ed25519 AAAA...',
            'default_zone': 'us-chi1', 'default_plan': 'STARTER-1xCPU-1GB',
            'default_template_uuid': '01000000-0000-4000-8000-000020070100',
        })
        cls.server = cls.env['deployment.server'].create({
            'name': 'New Dedicated VPS', 'hostname': 'placeholder.example.com',
            'kind': 'dedicated', 'vps_provider': 'upcloud',
            'upcloud_account_id': cls.account.id,
        })

    def _mock_upcloud_client(self):
        patcher = patch(
            'odoo.addons.managed_odoo_instances.models.upcloud_account.UpCloudClient')
        mock_cls = patcher.start()
        self.addCleanup(patcher.stop)
        return mock_cls.return_value

    def test_create_server_stores_uuid_and_ip(self):
        mock_client = self._mock_upcloud_client()
        mock_client.create_server.return_value = {
            'uuid': 'abc-123', 'state': 'maintenance',
            'ip_addresses': {'ip_address': [
                {'access': 'public', 'address': '203.0.113.5', 'family': 'IPv4'}]},
        }

        self.server.action_create_upcloud_server()

        self.assertEqual(self.server.upcloud_uuid, 'abc-123')
        self.assertEqual(self.server.upcloud_state, 'maintenance')
        self.assertEqual(self.server.hostname, '203.0.113.5')

    def test_create_server_passes_account_defaults_when_no_override(self):
        mock_client = self._mock_upcloud_client()
        mock_client.create_server.return_value = {
            'uuid': 'abc-123', 'state': 'maintenance', 'ip_addresses': {'ip_address': []}}

        self.server.action_create_upcloud_server()

        mock_client.create_server.assert_called_once()
        kwargs = mock_client.create_server.call_args[1]
        self.assertEqual(kwargs['zone'], 'us-chi1')
        self.assertEqual(kwargs['plan'], 'STARTER-1xCPU-1GB')
        self.assertEqual(kwargs['ssh_public_key'], 'ssh-ed25519 AAAA...')

    def test_create_server_per_server_override_wins(self):
        server = self.env['deployment.server'].create({
            'name': 'Override VPS', 'hostname': 'placeholder2.example.com',
            'kind': 'dedicated', 'vps_provider': 'upcloud',
            'upcloud_account_id': self.account.id, 'upcloud_zone': 'de-fra1',
        })
        mock_client = self._mock_upcloud_client()
        mock_client.create_server.return_value = {
            'uuid': 'xyz', 'state': 'maintenance', 'ip_addresses': {'ip_address': []}}

        server.action_create_upcloud_server()

        kwargs = mock_client.create_server.call_args[1]
        self.assertEqual(kwargs['zone'], 'de-fra1')

    def test_create_server_without_an_account_raises(self):
        server = self.env['deployment.server'].create({
            'name': 'No Account VPS', 'hostname': 'placeholder3.example.com',
            'kind': 'dedicated', 'vps_provider': 'upcloud',
        })
        with self.assertRaises(UserError):
            server.action_create_upcloud_server()

    def test_create_server_twice_raises(self):
        self.server.upcloud_uuid = 'already-created'
        with self.assertRaises(UserError):
            self.server.action_create_upcloud_server()

    def test_check_status_updates_the_stored_state(self):
        self.server.upcloud_uuid = 'abc-123'
        mock_client = self._mock_upcloud_client()
        mock_client.get_server.return_value = {'uuid': 'abc-123', 'state': 'started'}

        result = self.server.action_check_upcloud_status()

        self.assertEqual(self.server.upcloud_state, 'started')
        self.assertEqual(result['params']['type'], 'success')

    def test_check_status_without_a_vps_raises(self):
        with self.assertRaises(UserError):
            self.server.action_check_upcloud_status()

    def test_destroy_stops_waits_then_deletes(self):
        self.server.upcloud_uuid = 'abc-123'
        mock_client = self._mock_upcloud_client()

        self.server.action_destroy_upcloud_server()

        mock_client.stop_server.assert_called_once_with('abc-123')
        mock_client.wait_for_state.assert_called_once_with('abc-123', 'stopped')
        mock_client.delete_server.assert_called_once_with('abc-123', delete_storages=True)
        self.assertFalse(self.server.upcloud_uuid)
        self.assertFalse(self.server.upcloud_state)
