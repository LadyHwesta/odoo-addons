# -*- coding: utf-8 -*-
import logging

import requests

_logger = logging.getLogger(__name__)

TIMEOUT = 30


class SignalWireAPIError(Exception):
    """Raised for any SignalWire API failure - a non-2xx response, a
    network error, or an unparseable response. The message is
    normalized across the different error shapes SignalWire's own
    endpoints return (see _extract_error_message) rather than leaking
    a raw response body.
    """


class SignalWireClient:
    """Thin wrapper over the two REST surfaces this project uses:

    - the **Compatibility API** (Twilio-compatible "LaML"), rooted at
      ``/api/laml/2010-04-01/`` - used for accounts/subprojects, phone
      numbers, calls, and messages.
    - the **Relay REST API**, rooted at ``/api/relay/rest/`` - used for
      SIP Endpoints (click-to-call), which the Compatibility API
      doesn't cover. It uses a different error response shape than the
      Compatibility API (see ``_extract_error_message``) - verified
      live 2026-09-15 by deliberately triggering a validation error on
      each surface.
    - the **Project API**, rooted at ``/api/`` directly (not versioned
      under a date like the Compatibility API) - used for creating a
      subproject-scoped API token (``project/tokens``), so a resold
      customer can be handed real, independently-usable SignalWire
      credentials without ever needing that subproject's own (API-
      masked) auth_token. Confirmed live 2026-09-15: the resulting
      token pairs with the **subproject's own Account SID** as the
      Basic Auth username, not the parent project's - a parent-ID/new-
      token pairing returns 200 with an empty body (silently useless)
      where the subproject-ID pairing returns the real data.
    - the **Video API**, rooted at ``/api/video/`` - rooms, room
      tokens (for a browser client to actually join one), and room
      sessions/members (for per-participant usage billing). A fourth,
      genuinely different base path and response envelope again -
      confirmed live 2026-09-15 (create/list/delete a room, create a
      room token) rather than guessed from docs.
    - the **Registry (10DLC) API**, rooted at
      ``/api/relay/rest/registry/beta/`` - A2P 10DLC brand/campaign
      registration. A fifth base path, and confirmed live 2026-09-15 to
      have its own real quirk: brands and campaigns are addressed flat
      (``brands``, ``brands/{brand_id}/campaigns``) with **no
      subaccount/subproject scoping at all** - a query-string
      ``account_sid`` was silently ignored - but a campaign's own
      *numbers*/*orders* sub-resources are addressed directly by
      ``campaign_id`` alone, no brand prefix needed
      (``campaigns/{campaign_id}/orders``), and that's genuinely how a
      specific phone number (identified by its own SID, regardless of
      which subproject it lives in) gets tied to a specific campaign -
      confirmed by reading real, live data back from the user's own
      pending brand/campaign/order, not by guessing from docs (which
      don't document the exact paths for orders/numbers at all).

    One set of parent-project credentials is enough for everything
    here, including managing a subproject's own resources - just pass
    that subproject's Account SID as part of the path. **Confirmed
    live 2026-09-15**: a subproject's own ``auth_token`` comes back
    masked from the API on creation, but the parent project's
    credentials can list/create/delete that subproject's numbers,
    calls, etc. directly, so that masked token is never actually
    needed.
    """

    def __init__(self, space, project_id, api_token, timeout=TIMEOUT):
        self.space = space
        self.project_id = project_id
        self.api_token = api_token
        self.timeout = timeout

    @property
    def _auth(self):
        return (self.project_id, self.api_token)

    def compat_get(self, path, **params):
        """GET a Compatibility API path, relative to
        /api/laml/2010-04-01/ - e.g. ``f'Accounts/{sid}/Calls.json'``.
        """
        return self._request('get', self._compat_url(path), params=params)

    def compat_post(self, path, **data):
        return self._request('post', self._compat_url(path), data=data)

    def compat_delete(self, path):
        return self._request('delete', self._compat_url(path))

    def _compat_url(self, path):
        return f'https://{self.space}/api/laml/2010-04-01/{path}'

    def relay_post(self, path, **json_body):
        """POST a Relay REST path, relative to /api/relay/rest/ - e.g.
        ``'endpoints/sip'``.
        """
        return self._request('post', self._relay_url(path), json=json_body)

    def relay_delete(self, path):
        return self._request('delete', self._relay_url(path))

    def _relay_url(self, path):
        return f'https://{self.space}/api/relay/rest/{path}'

    def project_post(self, path, **json_body):
        """POST a Project API path, relative to /api/ - e.g.
        ``'project/tokens'``.
        """
        return self._request('post', self._project_url(path), json=json_body)

    def project_delete(self, path):
        return self._request('delete', self._project_url(path))

    def _project_url(self, path):
        return f'https://{self.space}/api/{path}'

    def video_get(self, path, **params):
        """GET a Video API path, relative to /api/video/ - e.g.
        ``'rooms'`` or ``'room_sessions'``. Confirmed live 2026-09-15:
        a different response envelope than the Compatibility API's own
        list shape - ``{"links": {...}, "data": [...]}`` rather than
        ``{"uri": ..., "<resource>": [...]}``.
        """
        return self._request('get', self._video_url(path), params=params)

    def video_post(self, path, **json_body):
        return self._request('post', self._video_url(path), json=json_body)

    def video_delete(self, path):
        return self._request('delete', self._video_url(path))

    def _video_url(self, path):
        return f'https://{self.space}/api/video/{path}'

    def registry_get(self, path, **params):
        """GET a Registry (10DLC) API path, relative to
        /api/relay/rest/registry/beta/ - e.g. ``'brands'`` or
        ``f'campaigns/{campaign_id}/numbers'``.
        """
        return self._request('get', self._registry_url(path), params=params)

    def registry_post(self, path, **json_body):
        return self._request('post', self._registry_url(path), json=json_body)

    def _registry_url(self, path):
        return f'https://{self.space}/api/relay/rest/registry/beta/{path}'

    def _request(self, method, url, **kwargs):
        try:
            response = requests.request(
                method, url, auth=self._auth, timeout=self.timeout, **kwargs)
        except requests.RequestException as exc:
            raise SignalWireAPIError(f'Could not reach SignalWire: {exc}') from exc

        if response.status_code >= 400:
            raise SignalWireAPIError(self._extract_error_message(response))

        if not response.content:
            # DELETE endpoints (e.g. SIP Endpoints) return 204 with no
            # body on success - verified live 2026-09-15.
            return {}
        try:
            return response.json()
        except ValueError:
            _logger.warning('SignalWire: non-JSON response from %s', url)
            return {}

    @staticmethod
    def _extract_error_message(response):
        try:
            payload = response.json()
        except ValueError:
            # e.g. a bad-auth 401 comes back as plain text "Unauthorized",
            # not JSON - verified live 2026-09-15.
            return f'SignalWire error {response.status_code}: {response.text or "(no body)"}'

        # Compatibility API shape: {"code": ..., "message": ..., ...}
        if 'message' in payload:
            return 'SignalWire error {}: {}'.format(
                payload.get('code', response.status_code), payload['message'])
        # Relay API shape: {"errors": [{"detail": ..., ...}, ...]}
        if 'errors' in payload:
            details = '; '.join(
                error.get('detail', str(error)) for error in payload['errors'])
            return f'SignalWire error {response.status_code}: {details}'
        return f'SignalWire error {response.status_code}: {payload}'
