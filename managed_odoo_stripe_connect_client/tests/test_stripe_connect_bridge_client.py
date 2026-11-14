# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

import requests
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.managed_odoo_stripe_connect_client.models.stripe_connect_bridge_client import (
    StripeConnectBridgeClient, StripeConnectBridgeError,
)


def _mock_response(status_code=200, json_body=None):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_body or {}
    return response


class TestStripeConnectBridgeClient(TransactionCase):

    def _client(self):
        return StripeConnectBridgeClient('https://meskis.net', 'tok-abc123')

    def test_create_onboarding_link_returns_the_url(self):
        client = self._client()
        with patch('requests.post', return_value=_mock_response(
                json_body={'url': 'https://connect.stripe.com/setup/abc'})) as post:
            url = client.create_onboarding_link()

        self.assertEqual(url, 'https://connect.stripe.com/setup/abc')
        args, kwargs = post.call_args
        self.assertEqual(args[0], 'https://meskis.net/stripe_connect_bridge/onboarding_link')
        self.assertEqual(kwargs['headers']['Authorization'], 'Bearer tok-abc123')

    def test_create_payment_intent_sends_amount_currency_and_reference(self):
        client = self._client()
        with patch('requests.post', return_value=_mock_response(
                json_body={'id': 'pi_123'})) as post:
            result = client.create_payment_intent(5000, 'usd', 'Invoice #1')

        self.assertEqual(result['id'], 'pi_123')
        args, kwargs = post.call_args
        self.assertEqual(args[0], 'https://meskis.net/stripe_connect_bridge/charge')
        self.assertEqual(
            kwargs['json'], {'amount': 5000, 'currency': 'usd', 'reference': 'Invoice #1'})

    def test_error_response_raises_with_the_bridges_own_message(self):
        client = self._client()
        with patch('requests.post', return_value=_mock_response(
                status_code=502, json_body={'error': 'account not active yet'})):
            with self.assertRaises(StripeConnectBridgeError) as cm:
                client.create_payment_intent(5000, 'usd', 'x')
        self.assertIn('account not active yet', str(cm.exception))

    def test_network_failure_raises_a_clear_error(self):
        client = self._client()
        with patch('requests.post', side_effect=requests.ConnectionError('boom')):
            with self.assertRaises(StripeConnectBridgeError):
                client.create_payment_intent(5000, 'usd', 'x')

    def test_trailing_slash_on_bridge_url_does_not_double_up(self):
        client = StripeConnectBridgeClient('https://meskis.net/', 'tok-abc123')
        with patch('requests.post', return_value=_mock_response(
                json_body={'url': 'https://connect.stripe.com/setup/abc'})) as post:
            client.create_onboarding_link()
        args, _ = post.call_args
        self.assertEqual(args[0], 'https://meskis.net/stripe_connect_bridge/onboarding_link')


@tagged('post_install', '-at_install')
class TestResCompanyStripeConnectBridge(TransactionCase):

    def test_get_client_without_configuration_raises_a_clear_error(self):
        company = self.env.company
        company.write({
            'stripe_connect_bridge_url': False, 'stripe_connect_bridge_token': False})
        with self.assertRaises(Exception):
            company._get_stripe_connect_bridge_client()

    def test_get_client_with_configuration_returns_a_working_client(self):
        company = self.env.company
        company.write({
            'stripe_connect_bridge_url': 'https://meskis.net',
            'stripe_connect_bridge_token': 'tok-abc123',
        })
        client = company._get_stripe_connect_bridge_client()
        self.assertIsInstance(client, StripeConnectBridgeClient)
        self.assertEqual(client.bridge_token, 'tok-abc123')
