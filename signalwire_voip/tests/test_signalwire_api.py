# -*- coding: utf-8 -*-
import json
from unittest.mock import MagicMock, patch

import requests
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.signalwire_voip.models.signalwire_api import (
    SignalWireAPIError, SignalWireClient,
)


def _mock_response(status_code=200, json_body=None, text_body='', content=b'x'):
    response = MagicMock()
    response.status_code = status_code
    response.content = content
    response.text = text_body
    if json_body is None:
        response.json.side_effect = ValueError('no json')
    else:
        response.json.return_value = json_body
    return response


@tagged('post_install', '-at_install')
class TestSignalWireClient(TransactionCase):

    def _client(self):
        return SignalWireClient(
            space='example.signalwire.com', project_id='pid123', api_token='tok456')

    def test_compat_get_hits_the_laml_url_with_basic_auth(self):
        client = self._client()
        with patch(
                'requests.request',
                return_value=_mock_response(json_body={'ok': True})) as req:
            client.compat_get('Accounts/pid123.json', Foo='bar')

        args, kwargs = req.call_args
        self.assertEqual(args[0], 'get')
        self.assertEqual(
            args[1], 'https://example.signalwire.com/api/laml/2010-04-01/Accounts/pid123.json')
        self.assertEqual(kwargs['auth'], ('pid123', 'tok456'))
        self.assertEqual(kwargs['params'], {'Foo': 'bar'})

    def test_compat_post_sends_form_data(self):
        client = self._client()
        with patch(
                'requests.request',
                return_value=_mock_response(json_body={'sid': 'abc'})) as req:
            result = client.compat_post('Accounts.json', FriendlyName='Test')

        args, kwargs = req.call_args
        self.assertEqual(args[0], 'post')
        self.assertEqual(kwargs['data'], {'FriendlyName': 'Test'})
        self.assertEqual(result, {'sid': 'abc'})

    def test_relay_post_hits_the_relay_url_as_json(self):
        client = self._client()
        with patch(
                'requests.request',
                return_value=_mock_response(json_body={'id': 'ep1'})) as req:
            client.relay_post('endpoints/sip', username='u', password='p')

        args, kwargs = req.call_args
        self.assertEqual(
            args[1], 'https://example.signalwire.com/api/relay/rest/endpoints/sip')
        self.assertEqual(kwargs['json'], {'username': 'u', 'password': 'p'})

    def test_project_post_hits_the_project_url_as_json(self):
        client = self._client()
        with patch(
                'requests.request',
                return_value=_mock_response(json_body={'token': 'swapi_abc'})) as req:
            client.project_post(
                'project/tokens', name='Customer', permissions=['messaging'],
                subproject_id='sub-1')

        args, kwargs = req.call_args
        self.assertEqual(
            args[1], 'https://example.signalwire.com/api/project/tokens')
        self.assertEqual(
            kwargs['json'],
            {'name': 'Customer', 'permissions': ['messaging'], 'subproject_id': 'sub-1'})

    def test_project_delete_hits_the_project_url(self):
        client = self._client()
        with patch(
                'requests.request', return_value=_mock_response(content=b'')) as req:
            client.project_delete('project/tokens/tok-1')

        args, kwargs = req.call_args
        self.assertEqual(args[0], 'delete')
        self.assertEqual(
            args[1], 'https://example.signalwire.com/api/project/tokens/tok-1')

    def test_delete_with_no_body_returns_empty_dict(self):
        # SIP Endpoint deletion returns 204 with no body - verified
        # live 2026-09-15.
        client = self._client()
        with patch(
                'requests.request',
                return_value=_mock_response(content=b'', json_body=None)):
            result = client.relay_delete('endpoints/sip/ep1')
        self.assertEqual(result, {})

    def test_compat_api_error_shape_surfaces_the_message(self):
        # {"code": ..., "message": ...} - verified live 2026-09-15
        # against a real validation error.
        client = self._client()
        with patch(
                'requests.request',
                return_value=_mock_response(
                    status_code=422,
                    json_body={'code': '21421', 'message': 'Phonenumber or AreaCode must be present.'})):
            with self.assertRaises(SignalWireAPIError) as cm:
                client.compat_post('Accounts/pid123/IncomingPhoneNumbers.json')
        self.assertIn('Phonenumber or AreaCode must be present.', str(cm.exception))

    def test_relay_api_error_shape_surfaces_the_details(self):
        # {"errors": [{"detail": ...}, ...]} - a DIFFERENT shape than
        # the Compatibility API's own errors, verified live 2026-09-15.
        client = self._client()
        with patch(
                'requests.request',
                return_value=_mock_response(
                    status_code=422,
                    json_body={'errors': [
                        {'detail': 'Username is required'},
                        {'detail': 'Password is required'},
                    ]})):
            with self.assertRaises(SignalWireAPIError) as cm:
                client.relay_post('endpoints/sip')
        message = str(cm.exception)
        self.assertIn('Username is required', message)
        self.assertIn('Password is required', message)

    def test_non_json_error_body_is_not_a_crash(self):
        # A bad-auth 401 comes back as plain text "Unauthorized", not
        # JSON - verified live 2026-09-15.
        client = self._client()
        with patch(
                'requests.request',
                return_value=_mock_response(
                    status_code=401, json_body=None, text_body='Unauthorized')):
            with self.assertRaises(SignalWireAPIError) as cm:
                client.compat_get('Accounts/pid123.json')
        self.assertIn('Unauthorized', str(cm.exception))

    def test_network_failure_raises(self):
        client = self._client()
        with patch('requests.request', side_effect=requests.ConnectionError('boom')):
            with self.assertRaises(SignalWireAPIError):
                client.compat_get('Accounts/pid123.json')
