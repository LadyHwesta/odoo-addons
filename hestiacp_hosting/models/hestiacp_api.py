# -*- coding: utf-8 -*-
"""Thin HTTP client for the HestiaCP API.

Isolated in its own module (not a mixin on hestiacp.server) so the wire
format is one small, easy-to-patch surface - both in tests (mock
HestiaCPClient.call directly) and in real life once this is checked
against a live server for the first time. HestiaCP's documented API
uses scoped "Access Keys" (Server > Access Keys in the UI), not a
full username/password: POST to https://host:8083/api/ with
access_key, secret_key, cmd, and arg1..argN as form fields.

**Not yet verified against a live HestiaCP instance** - built from
HestiaCP's documented API conventions. The request/response shape
here (field names, whether returncode=1 is needed, whether errors
come back as a non-200 status or as text in the body) should be
confirmed against a real server the first time hestiacp.server.test_connection()
is run for real, and this file adjusted if anything's off - that's
deliberately the only place such a fix should be needed.
"""
import logging

import requests

from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

TIMEOUT = 30


class HestiaCPAPIError(UserError):
    """Raised when a HestiaCP API call fails or returns an error."""


class HestiaCPClient:
    """Call a single HestiaCP server's API.

    :param base_url: e.g. "https://host.example.com:8083"
    :param access_key: the public half of a HestiaCP Access Key
    :param secret_key: the secret half
    """

    def __init__(self, base_url, access_key, secret_key):
        self.base_url = base_url.rstrip('/')
        self.access_key = access_key
        self.secret_key = secret_key

    def call(self, cmd, *args):
        """Run a single HestiaCP ``v-*`` command and return its raw text
        output (same as what the CLI command would print), with a
        trailing newline stripped.

        :raises HestiaCPAPIError: on a network failure or a non-zero
            HestiaCP return code.
        """
        payload = {
            'access_key': self.access_key,
            'secret_key': self.secret_key,
            'cmd': cmd,
            'returncode': 'yes',
        }
        for i, arg in enumerate(args, start=1):
            payload[f'arg{i}'] = '' if arg is None else str(arg)

        url = f'{self.base_url}/api/'
        try:
            response = requests.post(url, data=payload, timeout=TIMEOUT)
        except requests.RequestException as exc:
            _logger.warning('HestiaCP API request failed (%s %s): %s', cmd, args, exc)
            raise HestiaCPAPIError(
                f'Could not reach the HestiaCP server: {exc}'
            ) from exc

        text = response.text.strip()
        if response.status_code != 200:
            raise HestiaCPAPIError(
                f'HestiaCP returned HTTP {response.status_code} for {cmd}: {text}'
            )

        # With returncode=yes, HestiaCP appends the numeric shell exit
        # code as the last line of output (0 = success). Split it off
        # rather than assuming the whole body is just that code, since
        # list/status commands return real output plus the code.
        lines = text.splitlines()
        if lines and lines[-1].strip().lstrip('-').isdigit():
            code = int(lines[-1].strip())
            body = '\n'.join(lines[:-1])
        else:
            # Unexpected shape - treat the whole response as the body
            # and don't assume success.
            code, body = None, text

        if code not in (0, None):
            raise HestiaCPAPIError(
                f'HestiaCP command {cmd} failed (exit {code}): {body}'
            )
        return body
