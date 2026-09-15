# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

import requests
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.managed_odoo_instances.models.deployment_agent_client import (
    DeploymentAgentClient, DeploymentAgentError)


@tagged('post_install', '-at_install')
class TestDeploymentAgentClient(TransactionCase):

    def setUp(self):
        super().setUp()
        self.client = DeploymentAgentClient('https://vps1.example.com:8765', 'test-token')

    def test_create_vhost_sends_the_right_payload_and_auth(self):
        with patch('requests.post') as mock_post:
            mock_post.return_value = MagicMock(status_code=200, content=b'{"status": "created"}',
                                                 json=lambda: {'status': 'created'})
            self.client.create_vhost('customer.example.com', 'customer_db')

        args, kwargs = mock_post.call_args
        assert args[0] == 'https://vps1.example.com:8765/vhosts'
        assert kwargs['json'] == {'domain': 'customer.example.com', 'db_name': 'customer_db'}
        assert kwargs['headers']['Authorization'] == 'Bearer test-token'

    def test_health_needs_no_auth_header(self):
        with patch('requests.get') as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200, json=lambda: {'status': 'ok', 'version': '0.1.0'})
            result = self.client.health()

        args, kwargs = mock_get.call_args
        assert args[0] == 'https://vps1.example.com:8765/health'
        assert 'headers' not in kwargs
        assert result['version'] == '0.1.0'

    def test_network_failure_raises_deployment_agent_error(self):
        with patch('requests.post', side_effect=requests.ConnectionError('refused')):
            with self.assertRaises(DeploymentAgentError):
                self.client.create_vhost('customer.example.com', 'customer_db')

    def test_error_response_surfaces_the_agents_own_detail_message(self):
        with patch('requests.post') as mock_post:
            mock_post.return_value = MagicMock(
                status_code=422, content=b'{"detail": "invalid domain"}',
                text='{"detail": "invalid domain"}',
                json=lambda: {'detail': 'invalid domain'})
            with self.assertRaises(DeploymentAgentError) as cm:
                self.client.create_vhost('bad domain', 'customer_db')

        self.assertIn('invalid domain', str(cm.exception))

    def test_health_check_failure_raises(self):
        with patch('requests.get') as mock_get:
            mock_get.return_value = MagicMock(status_code=503)
            with self.assertRaises(DeploymentAgentError):
                self.client.health()
