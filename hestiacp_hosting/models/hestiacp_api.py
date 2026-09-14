# -*- coding: utf-8 -*-
"""Thin HTTP client for the HestiaCP API.

Isolated in its own module (not a mixin on hestiacp.server) so the wire
format is one small surface, kept correct in one place for both tests
(mock HestiaCPClient.call directly) and the model code that uses it.

**Verified against a live HestiaCP instance on 2026-09-14** (a full
v-add-user -> v-suspend-user -> v-unsuspend-user -> v-list-user ->
v-delete-user cycle against a real server), against HestiaCP's actual
web/api/index.php and func/main.sh source, not just its docs page:

- POST to https://host:port/api/ with access_key, secret_key, cmd, and
  arg1..argN as form fields - this part matched the original
  assumption exactly.
- Do **not** send returncode=yes: it makes HestiaCP discard the actual
  command output and return only the bare exit code instead - fine for
  action commands (v-add-user etc., which return nothing on success
  anyway) but silently breaks any v-list-* command's real data, which
  callers need.
- The reliable way to check success/failure is the always-present
  ``Hestia-Exit-Code`` response header (0 = success), not the response
  body or HTTP status code alone - HestiaCP maps its exit codes to a
  range of HTTP statuses (e.g. 401 for an auth/permission failure, 422
  for a bad argument), so status-code-only handling isn't uniform, but
  the header always carries the real HestiaCP exit code.
- On failure the body is a human-readable "Error: ..." message. On
  success it's either empty (action commands) or the actual output
  (e.g. JSON for a `v-list-*` command with a `json` format argument).
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
        output (same as what the CLI command would print - empty for
        most action commands, real data for a `v-list-*` command).

        :raises HestiaCPAPIError: on a network failure or a non-zero
            HestiaCP exit code.
        """
        payload = {
            'access_key': self.access_key,
            'secret_key': self.secret_key,
            'cmd': cmd,
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

        body = response.text.strip()
        exit_code_header = response.headers.get('Hestia-Exit-Code')
        try:
            code = int(exit_code_header)
        except (TypeError, ValueError):
            raise HestiaCPAPIError(
                f'Unexpected response from HestiaCP for {cmd} (HTTP '
                f'{response.status_code}, no valid Hestia-Exit-Code header): {body}'
            ) from None

        if code != 0:
            raise HestiaCPAPIError(f'HestiaCP command {cmd} failed (exit {code}): {body}')
        return body
