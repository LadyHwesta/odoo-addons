# -*- coding: utf-8 -*-
"""Thin HTTP client for UpCloud's API (https://developers.upcloud.com/1.3/).
Isolated in its own module, same reasoning as every other API client in
this repo (HestiaCPClient, SignalWireClient, DeploymentAgentClient) -
one small wire-format surface, kept correct in one place.

**Live-verified 2026-09-15** against the user's real UpCloud account:
created a real STARTER-1xCPU-1GB server in us-chi1 from the Debian 12
template, confirmed it actually came up (SSH login with the injected
key worked, real Debian 12 install), then stopped and deleted it
(server + storage) - confirmed gone via a follow-up 404. Two real
findings that don't match a naive reading of the docs:

- ``metadata`` in the create-server request body must be the literal
  **string** ``"yes"``, not a JSON boolean - ``true`` is rejected with
  ``METADATA_INVALID``. Needed at all because cloning a cloud-init-
  based template (which the standard Debian/Ubuntu templates are)
  fails outright with ``METADATA_DISABLED_ON_CLOUD-INIT`` without it.
- The server reaching ``state: started`` does **not** mean SSH is
  actually reachable yet - a real attempt got "Connection refused"
  immediately after ``started``, and only succeeded ~15s later.
  ``wait_for_ssh_ready`` bakes in that extra wait/retry rather than
  treating ``started`` alone as "ready."
"""
import logging
import time

import requests

from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

BASE_URL = 'https://api.upcloud.com'
TIMEOUT = 30


class UpCloudAPIError(UserError):
    """Raised when the UpCloud API is unreachable or returns an error."""


class UpCloudClient:
    """:param token: an UpCloud API token (the ``ucat_...`` kind, created
        in the UpCloud control panel or via ``upctl`` - not a
        subaccount username/password).
    """

    def __init__(self, token):
        self.token = token

    def _request(self, method, path, json_body=None, params=None):
        url = f'{BASE_URL}{path}'
        try:
            response = requests.request(
                method, url, json=json_body, params=params, timeout=TIMEOUT,
                headers={'Authorization': f'Bearer {self.token}'})
        except requests.RequestException as exc:
            _logger.warning('UpCloud API request failed (%s %s): %s', method, path, exc)
            raise UpCloudAPIError(f'Could not reach the UpCloud API: {exc}') from exc

        if response.status_code >= 400:
            detail = response.text
            try:
                detail = response.json().get('error', {}).get('error_message', detail)
            except ValueError:
                pass
            raise UpCloudAPIError(
                f'UpCloud API request to {path} failed '
                f'(HTTP {response.status_code}): {detail}')
        return response.json() if response.content else {}

    def list_zones(self):
        result = self._request('GET', '/1.3/zone')
        return [z['id'] for z in result.get('zones', {}).get('zone', [])]

    def list_plans(self):
        result = self._request('GET', '/1.3/plan')
        return result.get('plans', {}).get('plan', [])

    def create_server(self, zone, plan, template_uuid, title, hostname, ssh_public_key,
                       username='root', storage_size=10):
        """Creates a real server (real money) and returns the API's own
        response dict for it - state will be "maintenance", not
        "started", immediately after this returns; poll get_server()
        (or use wait_for_started()) for actual readiness.
        """
        body = {
            'server': {
                'zone': zone,
                'title': title,
                'hostname': hostname,
                'plan': plan,
                # String "yes", not a JSON boolean - see this module's
                # own docstring for why (confirmed live).
                'metadata': 'yes',
                'storage_devices': {
                    'storage_device': [{
                        'action': 'clone',
                        'storage': template_uuid,
                        'title': f'{title}-os',
                        'size': storage_size,
                        'tier': 'standard',
                    }],
                },
                'networking': {
                    'interfaces': {
                        'interface': [{
                            'type': 'public',
                            'ip_addresses': {'ip_address': [{'family': 'IPv4'}]},
                        }],
                    },
                },
                'login_user': {
                    'username': username,
                    'ssh_keys': {'ssh_key': [ssh_public_key]},
                },
            },
        }
        result = self._request('POST', '/1.3/server', json_body=body)
        return result['server']

    def get_server(self, uuid):
        result = self._request('GET', f'/1.3/server/{uuid}')
        return result['server']

    def stop_server(self, uuid):
        self._request('POST', f'/1.3/server/{uuid}/stop', json_body={
            'stop_server': {'stop_type': 'hard'}})

    def delete_server(self, uuid, delete_storages=True):
        params = {'storages': 1} if delete_storages else None
        self._request('DELETE', f'/1.3/server/{uuid}', params=params)

    def wait_for_state(self, uuid, state, timeout=180, poll_interval=5):
        """Polls get_server() until it reaches `state` or timeout -
        needed for stop_server() specifically (confirmed live: its
        response, like create_server()'s, reports the server's state
        from *before* the action finishes - a delete_server() call
        made immediately after stop_server() without waiting for
        "stopped" isn't guaranteed to succeed). Not used by
        action_create_upcloud_server/action_check_upcloud_status
        (those deliberately return right away rather than blocking an
        HTTP request for up to a few minutes) - only by
        action_destroy_upcloud_server, a rare, one-off admin action
        where waiting a few seconds for correctness matters more.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            server = self.get_server(uuid)
            if server['state'] == state:
                return server
            time.sleep(poll_interval)
        raise UpCloudAPIError(
            f'Server {uuid} did not reach "{state}" within {timeout}s.')
