# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.namecheap_domains.models.namecheap_api import (
    NamecheapAPIError, NamecheapClient,
)

# Namecheap's real response namespaces every element via the root's
# default xmlns - not independently verified against a live call yet
# (see namecheap_api.py's own docstring), built from a real third-party
# client's actual parsing code instead. These fixtures exist to prove
# the client's namespace-stripping and error handling work against
# that shape; the shape itself gets its real verification against the
# sandbox, same discipline as hestiacp_api.py.
SUCCESS_XML = b"""<?xml version="1.0" encoding="utf-8"?>
<ApiResponse xmlns="http://api.namecheap.com/xml.response" Status="OK">
  <Errors />
  <CommandResponse Type="namecheap.domains.check">
    <DomainCheckResult Domain="example.com" Available="false" IsPremiumName="false" />
    <DomainCheckResult Domain="available123.com" Available="true" IsPremiumName="false" />
    <DomainCheckResult Domain="premium.com" Available="true" IsPremiumName="true"
                        PremiumRegistrationPrice="500.00" />
  </CommandResponse>
</ApiResponse>
"""

ERROR_XML = b"""<?xml version="1.0" encoding="utf-8"?>
<ApiResponse xmlns="http://api.namecheap.com/xml.response" Status="ERROR">
  <Errors>
    <Error Number="1011150">Invalid request IP</Error>
  </Errors>
  <RequestedCommand>namecheap.domains.check</RequestedCommand>
</ApiResponse>
"""


def _mock_response(content, status_code=200):
    response = MagicMock()
    response.content = content
    response.text = content.decode()
    response.status_code = status_code
    return response


@tagged('post_install', '-at_install')
class TestNamecheapClient(TransactionCase):

    def _client(self):
        return NamecheapClient(
            api_user='tester', api_key='key123', username='tester',
            client_ip='1.2.3.4', sandbox=True)

    def test_call_sends_expected_form_fields(self):
        client = self._client()
        with patch('requests.post', return_value=_mock_response(SUCCESS_XML)) as post:
            client.call('namecheap.domains.check', DomainList='example.com')

        args, kwargs = post.call_args
        self.assertIn('sandbox', args[0])
        self.assertEqual(kwargs['data']['ApiUser'], 'tester')
        self.assertEqual(kwargs['data']['ApiKey'], 'key123')
        self.assertEqual(kwargs['data']['ClientIP'], '1.2.3.4')
        self.assertEqual(kwargs['data']['Command'], 'namecheap.domains.check')
        self.assertEqual(kwargs['data']['DomainList'], 'example.com')

    def test_call_strips_the_namespace_so_plain_tags_work(self):
        client = self._client()
        with patch('requests.post', return_value=_mock_response(SUCCESS_XML)):
            result = client.call('namecheap.domains.check')

        # find('DomainCheckResult') only works if the namespace was
        # actually stripped - a namespaced-but-unstripped tree would
        # silently return nothing here instead of raising
        results = result.findall('DomainCheckResult')
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0].get('Domain'), 'example.com')

    def test_error_status_raises_with_the_real_message(self):
        client = self._client()
        with patch('requests.post', return_value=_mock_response(ERROR_XML)):
            with self.assertRaises(NamecheapAPIError) as cm:
                client.call('namecheap.domains.check')
        self.assertIn('Invalid request IP', str(cm.exception))

    def test_non_xml_response_raises_a_clear_error(self):
        client = self._client()
        with patch('requests.post', return_value=_mock_response(b'<not valid xml')):
            with self.assertRaises(NamecheapAPIError):
                client.call('namecheap.domains.check')

    def test_network_failure_raises(self):
        import requests
        client = self._client()
        with patch('requests.post', side_effect=requests.ConnectionError('boom')):
            with self.assertRaises(NamecheapAPIError):
                client.call('namecheap.domains.check')

    def test_sandbox_and_production_use_different_urls(self):
        sandbox = NamecheapClient('u', 'k', 'u', '1.2.3.4', sandbox=True)
        production = NamecheapClient('u', 'k', 'u', '1.2.3.4', sandbox=False)
        self.assertIn('sandbox', sandbox.base_url)
        self.assertNotIn('sandbox', production.base_url)
