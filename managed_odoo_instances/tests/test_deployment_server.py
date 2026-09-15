# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.managed_odoo_instances.models.deployment_agent_client import (
    DeploymentAgentError)


@tagged('post_install', '-at_install')
class TestDeploymentServer(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['deployment.server'].create({
            'name': 'Shared Server', 'hostname': 'shared.example.com',
            'kind': 'shared', 'agent_url': 'https://shared.example.com:8765',
        })

    def test_get_client_without_a_token_raises_a_clear_error(self):
        with self.assertRaises(UserError) as cm:
            self.server._get_client()
        self.assertIn('agent token', str(cm.exception))

    def test_get_client_with_a_token_returns_a_working_client(self):
        self.server.agent_token = 'real-token'
        client = self.server._get_client()
        self.assertEqual(client.base_url, 'https://shared.example.com:8765')
        self.assertEqual(client.token, 'real-token')

    def test_test_connection_success_records_health_and_returns_a_notification(self):
        self.server.agent_token = 'real-token'
        with patch(
                'odoo.addons.managed_odoo_instances.models.deployment_server.'
                'DeploymentAgentClient') as mock_client_cls:
            mock_client_cls.return_value.health.return_value = {
                'status': 'ok', 'version': '0.1.0'}
            result = self.server.action_test_connection()

        self.assertEqual(result['params']['type'], 'success')
        self.assertIn('0.1.0', result['params']['message'])
        self.assertTrue(self.server.last_health_ok)
        self.assertTrue(self.server.last_health_check)

    def test_test_connection_failure_records_health_and_returns_a_notification(self):
        self.server.agent_token = 'real-token'
        with patch(
                'odoo.addons.managed_odoo_instances.models.deployment_server.'
                'DeploymentAgentClient') as mock_client_cls:
            mock_client_cls.return_value.health.side_effect = DeploymentAgentError(
                'unreachable')
            result = self.server.action_test_connection()

        self.assertEqual(result['params']['type'], 'danger')
        self.assertFalse(self.server.last_health_ok)
        self.assertTrue(self.server.last_health_check)

    def test_test_connection_never_raises_even_on_failure(self):
        """The whole point of returning a notification instead of
        raising: a health-check failure is expected, not exceptional,
        and raising here would roll back the write() above it (see
        deployment_server.py's own docstring on this method).
        """
        self.server.agent_token = 'real-token'
        with patch(
                'odoo.addons.managed_odoo_instances.models.deployment_server.'
                'DeploymentAgentClient') as mock_client_cls:
            mock_client_cls.return_value.health.side_effect = DeploymentAgentError(
                'unreachable')
            try:
                self.server.action_test_connection()
            except DeploymentAgentError:
                self.fail("action_test_connection should not raise on a failed health check")
