# -*- coding: utf-8 -*-
"""Thin HTTP client for Namecheap's reseller API.

Namecheap's API (https://www.namecheap.com/support/api/intro/) is XML
over HTTP POST, not REST/JSON: every request sends ApiUser/ApiKey/
UserName/ClientIP/Command (+ command-specific params) as form data to
https://api.namecheap.com/xml.response (or api.sandbox.namecheap.com
for the separate sandbox environment - a different account signup
entirely, unconnected to a real Namecheap account, with fake domains
and fake money). A successful response is
<ApiResponse Status="OK">...<CommandResponse>...</CommandResponse></ApiResponse>;
a failed one is Status="ERROR" with <Errors><Error Number="...">
message</Error></Errors>.

**Not independently verified against a live call yet** (unlike
hestiacp_api.py, which was checked against HestiaCP's own GitHub
source and a real server) - Namecheap's own docs pages return HTTP 403
to automated fetching, so this is built from a real third-party open-
source client's actual request/parse code instead, cross-checked
against Namecheap's community-documented parameter names. Treat the
first sandbox call as the real verification, and update this docstring
with whatever comes out different, the same way hestiacp_api.py's did.

Two things that aren't obvious from a first read of the docs:
- The calling server's IP must be added to the account's API IP
  whitelist (up to 10 IPv4 addresses, IPv4 only) before ANY call
  succeeds - an otherwise-correct request fails with an unhelpful
  "API Key is invalid" - style error if this hasn't been done, easy to
  mistake for a bad key rather than a missing whitelist entry.
- Real production API access is itself gated: the account needs 20+
  domains under management, OR $50+ balance, OR $50+ spent in the last
  2 years, before Namecheap turns it on. The sandbox has no such gate.
- Every element in the XML response - not just the root - is in the
  ``http://api.namecheap.com/xml.response`` namespace, which makes a
  plain ElementTree.find('Tag') silently return nothing unless the
  namespace is spelled out on every lookup; stripped once up front here
  instead of threading {namespace} into every call site.
"""
import logging
from xml.etree import ElementTree

import requests

from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

TIMEOUT = 30
PRODUCTION_URL = 'https://api.namecheap.com/xml.response'
SANDBOX_URL = 'https://api.sandbox.namecheap.com/xml.response'


class NamecheapAPIError(UserError):
    """Raised when a Namecheap API call fails or returns an error."""


class NamecheapClient:
    """Call Namecheap's reseller API.

    :param api_user: the Namecheap account username that owns the key
    :param api_key: the API key generated for that account
    :param username: almost always the same as api_user - Namecheap
        keeps them separate to support reseller sub-accounts, where a
        parent account's key can act on behalf of a different UserName
    :param client_ip: this server's own whitelisted IP
    :param sandbox: use the sandbox environment instead of production
    """

    def __init__(self, api_user, api_key, username, client_ip, sandbox=False):
        self.api_user = api_user
        self.api_key = api_key
        self.username = username
        self.client_ip = client_ip
        self.base_url = SANDBOX_URL if sandbox else PRODUCTION_URL

    def call(self, command, **params):
        """Run a single Namecheap command and return its
        ``CommandResponse`` element (namespace already stripped, so
        children can be found by plain tag name, e.g.
        ``result.find('DomainCheckResult')``).

        :raises NamecheapAPIError: on a network failure, a malformed
            response, or an ERROR status.
        """
        data = {
            'ApiUser': self.api_user,
            'ApiKey': self.api_key,
            'UserName': self.username,
            'ClientIP': self.client_ip,
            'Command': command,
        }
        data.update({k: v for k, v in params.items() if v is not None})

        try:
            response = requests.post(self.base_url, data=data, timeout=TIMEOUT)
        except requests.RequestException as exc:
            _logger.warning('Namecheap API request failed (%s): %s', command, exc)
            raise NamecheapAPIError(f'Could not reach Namecheap: {exc}') from exc

        try:
            root = _strip_namespace(ElementTree.fromstring(response.content))
        except ElementTree.ParseError as exc:
            raise NamecheapAPIError(
                f'Unexpected (non-XML) response from Namecheap for {command}: '
                f'{response.text[:500]}'
            ) from exc

        if root.get('Status') != 'OK':
            error = root.find('Errors/Error')
            message = error.text if error is not None else 'Unknown error'
            raise NamecheapAPIError(f'Namecheap command {command} failed: {message}')

        return root.find('CommandResponse')


def _strip_namespace(element):
    for el in element.iter():
        if '}' in el.tag:
            el.tag = el.tag.split('}', 1)[1]
    return element
