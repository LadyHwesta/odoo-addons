# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

import requests
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.managed_odoo_instances.models.upcloud_client import (
    UpCloudAPIError, UpCloudClient)


@tagged('post_install', '-at_install')
class TestUpCloudClient(TransactionCase):

    def setUp(self):
        super().setUp()
        self.client = UpCloudClient('ucat_test_token')

    def test_create_server_sends_metadata_as_the_string_yes_not_a_boolean(self):
        """Confirmed live 2026-09-15: a JSON boolean is rejected
        outright (METADATA_INVALID) - only the literal string "yes"
        works, needed at all because the standard Debian/Ubuntu
        templates are cloud-init-based (METADATA_DISABLED_ON_CLOUD-INIT
        otherwise). The single most important thing this test file
        guards against regressing.
        """
        with patch('requests.request') as mock_request:
            mock_request.return_value = MagicMock(
                status_code=202, content=b'{"server": {"uuid": "abc", "state": "maintenance"}}',
                json=lambda: {'server': {'uuid': 'abc', 'state': 'maintenance'}})
            self.client.create_server(
                zone='us-chi1', plan='STARTER-1xCPU-1GB',
                template_uuid='01000000-0000-4000-8000-000020070100',
                title='test-server', hostname='test.example.com',
                ssh_public_key='ssh-ed25519 AAAA...')

        _method, _url = mock_request.call_args[0]
        body = mock_request.call_args[1]['json']
        self.assertEqual(body['server']['metadata'], 'yes')
        self.assertIsInstance(body['server']['metadata'], str)

    def test_create_server_sends_the_right_shape(self):
        with patch('requests.request') as mock_request:
            mock_request.return_value = MagicMock(
                status_code=202,
                content=b'{"server": {"uuid": "abc", "state": "maintenance"}}',
                json=lambda: {'server': {'uuid': 'abc', 'state': 'maintenance'}})
            self.client.create_server(
                zone='us-chi1', plan='STARTER-1xCPU-1GB',
                template_uuid='01000000-0000-4000-8000-000020070100',
                title='test-server', hostname='test.example.com',
                ssh_public_key='ssh-ed25519 AAAA...')

        method, url = mock_request.call_args[0]
        kwargs = mock_request.call_args[1]
        self.assertEqual(method, 'POST')
        self.assertEqual(url, 'https://api.upcloud.com/1.3/server')
        self.assertEqual(kwargs['headers']['Authorization'], 'Bearer ucat_test_token')
        server = kwargs['json']['server']
        self.assertEqual(server['zone'], 'us-chi1')
        self.assertEqual(server['plan'], 'STARTER-1xCPU-1GB')
        self.assertEqual(server['hostname'], 'test.example.com')
        self.assertEqual(
            server['storage_devices']['storage_device'][0]['storage'],
            '01000000-0000-4000-8000-000020070100')
        self.assertEqual(
            server['login_user']['ssh_keys']['ssh_key'], ['ssh-ed25519 AAAA...'])

    def test_create_server_returns_the_server_dict(self):
        with patch('requests.request') as mock_request:
            mock_request.return_value = MagicMock(
                status_code=202,
                content=b'{"server": {"uuid": "abc-123", "state": "maintenance"}}',
                json=lambda: {'server': {'uuid': 'abc-123', 'state': 'maintenance'}})
            result = self.client.create_server(
                zone='us-chi1', plan='STARTER-1xCPU-1GB',
                template_uuid='01000000-0000-4000-8000-000020070100',
                title='t', hostname='h', ssh_public_key='k')

        self.assertEqual(result['uuid'], 'abc-123')
        self.assertEqual(result['state'], 'maintenance')

    def test_error_response_surfaces_the_real_error_message(self):
        with patch('requests.request') as mock_request:
            mock_request.return_value = MagicMock(
                status_code=409,
                content=b'{"error": {"error_code": "X", "error_message": "boom"}}',
                text='{"error": {"error_code": "X", "error_message": "boom"}}',
                json=lambda: {'error': {'error_code': 'X', 'error_message': 'boom'}})
            with self.assertRaises(UpCloudAPIError) as cm:
                self.client.create_server(
                    zone='z', plan='p', template_uuid='t',
                    title='t', hostname='h', ssh_public_key='k')

        self.assertIn('boom', str(cm.exception))

    def test_network_failure_raises(self):
        with patch('requests.request', side_effect=requests.ConnectionError('refused')):
            with self.assertRaises(UpCloudAPIError):
                self.client.list_zones()

    def test_delete_server_passes_storages_param(self):
        with patch('requests.request') as mock_request:
            mock_request.return_value = MagicMock(status_code=204, content=b'')
            self.client.delete_server('abc-123', delete_storages=True)

        method, url = mock_request.call_args[0]
        self.assertEqual(method, 'DELETE')
        self.assertEqual(url, 'https://api.upcloud.com/1.3/server/abc-123')
        self.assertEqual(mock_request.call_args[1]['params'], {'storages': 1})

    def test_wait_for_state_polls_until_the_target_state(self):
        states = iter(['maintenance', 'maintenance', 'stopped'])
        with patch.object(self.client, 'get_server', side_effect=lambda uuid: {
                'uuid': uuid, 'state': next(states)}):
            with patch('time.sleep'):
                result = self.client.wait_for_state('abc-123', 'stopped', poll_interval=0)

        self.assertEqual(result['state'], 'stopped')

    def test_wait_for_state_times_out(self):
        with patch.object(self.client, 'get_server',
                           return_value={'uuid': 'abc', 'state': 'maintenance'}):
            with patch('time.sleep'):
                with self.assertRaises(UpCloudAPIError):
                    self.client.wait_for_state('abc-123', 'started', timeout=0, poll_interval=0)
