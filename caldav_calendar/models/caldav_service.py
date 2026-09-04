# -*- coding: utf-8 -*-
"""Minimal RFC 4791 (CalDAV) / RFC 6578 (WebDAV sync-collection) client.

This is a plain-Python helper, deliberately independent of the Odoo ORM, so
it can be unit tested and reused outside of a request context (e.g. from a
cron worker). It only depends on ``requests`` and ``lxml``, both of which
are already core Odoo dependencies - no extra pip install is required.
"""
import logging
import time
from urllib.parse import urljoin, urlparse
from xml.sax.saxutils import escape as xml_escape

import requests
from lxml import etree

_logger = logging.getLogger(__name__)

NS = {
    'd': 'DAV:',
    'c': 'urn:ietf:params:xml:ns:caldav',
}

# requests timeout as (connect, read). The connect budget stays short - a
# server that won't even accept the socket in 10s isn't going to get better -
# but the read budget is generous: a CalDAV sync-collection REPORT makes the
# server compute a whole change set, and a cold PHP/DB backend (Nextcloud et
# al.) can legitimately take a while just to send the first byte.
CONNECT_TIMEOUT = 10
DEFAULT_READ_TIMEOUT = 90

# Transient network failures (timeout, dropped connection) are retried this
# many extra times, with exponential backoff, before giving up. Every request
# this client makes is safe to replay: GET/PROPFIND/REPORT are read-only, and
# PUT/DELETE both carry ETag preconditions (or If-None-Match:* on create), so
# a retry after a response we never saw resolves as a 412/404 the callers
# already handle rather than as a duplicate write.
RETRIES = 2
RETRY_BACKOFF = 1.0


class CalDAVError(Exception):
    """Base error for any CalDAV/WebDAV failure."""


class CalDAVAuthError(CalDAVError):
    """401/403 - bad credentials."""


class CalDAVNotFoundError(CalDAVError):
    """404 - the resource / collection does not exist."""


class CalDAVPreconditionFailedError(CalDAVError):
    """412/423 - ETag precondition failed: the resource changed remotely."""


class CalDAVSyncTokenInvalidError(CalDAVError):
    """RFC 6578 Sec 3.2 valid-sync-token precondition failure on a
    sync-collection REPORT: token expired/unknown, do a full resync."""


class CalDAVConnectionError(CalDAVError):
    """The request never got a usable HTTP response: connection refused/reset,
    DNS failure, TLS error, or a read/connect timeout that outlasted the
    retries. Distinct from an HTTP error status, which means the server did
    answer."""


def _raise_for_status(response):
    # Note: a 403 on a sync-collection REPORT that actually carries the
    # RFC 6578 valid-sync-token precondition is intercepted earlier, in
    # CalDAVClient._request(), and raised as CalDAVSyncTokenInvalidError
    # instead - any 401/403 that reaches here (including a sync-collection
    # 403 with no such precondition) is a genuine auth failure.
    if response.status_code in (401, 403):
        raise CalDAVAuthError(f'{response.status_code} {response.reason} for {response.url}')
    if response.status_code == 404:
        raise CalDAVNotFoundError(f'404 Not Found for {response.url}')
    if response.status_code in (412, 423):
        raise CalDAVPreconditionFailedError(f'{response.status_code} {response.reason} for {response.url}')
    if response.status_code >= 400:
        raise CalDAVError(f'{response.status_code} {response.reason} for {response.url}: {response.text[:500]}')


def _text(el):
    return el.text.strip() if el is not None and el.text else False


def _is_invalid_sync_token_error(response):
    """RFC 6578 Sec 3.2: a sync-collection REPORT with an expired/unknown
    sync-token fails with 403 Forbidden and a DAV:valid-sync-token
    precondition element in a DAV:error response body - distinct from a
    plain 403 caused by a genuine authorization failure, which carries no
    such body. Match by local name only: some servers don't bind the
    DAV: namespace to the `d` prefix used elsewhere in this client.
    """
    try:
        root = etree.fromstring(response.content)
    except etree.XMLSyntaxError:
        return False
    return bool(root.xpath('//*[local-name()="valid-sync-token"]'))


def _find_ctag(el):
    # getctag lives in the non-standard "http://calendarserver.org/ns/" namespace,
    # but some servers advertise it under a different prefix/URI, so match by
    # local name only. .find()'s limited ElementPath doesn't support
    # local-name(), so this needs the full .xpath() API.
    results = el.xpath('.//*[local-name()="getctag"]')
    return results[0].text.strip() if results and results[0].text else False


class CalDAVClient:
    """Thin wrapper around a `requests.Session` speaking WebDAV/CalDAV XML."""

    def __init__(self, url, username, password, timeout=None):
        parsed = urlparse(url)
        self.base_url = f'{parsed.scheme}://{parsed.netloc}'
        self.calendar_url = url if url.endswith('/') else url + '/'
        self.timeout = (CONNECT_TIMEOUT, timeout or DEFAULT_READ_TIMEOUT)
        self.session = requests.Session()
        # A public/shared read-only calendar may need no auth at all; skip the
        # Basic-Auth header entirely rather than sending an empty credential.
        # A username with no password is still allowed (some servers take a
        # token as the username).
        if username:
            self.session.auth = (username, password or '')
        self.session.headers['User-Agent'] = 'Odoo CalDAV Calendar Sync'

    # ------------------------------------------------------------------
    # Low level requests
    # ------------------------------------------------------------------
    def _request(self, method, url, headers=None, data=None, depth=None, is_sync_collection=False):
        headers = dict(headers or {})
        if depth is not None:
            headers['Depth'] = str(depth)
        payload = data.encode('utf-8') if isinstance(data, str) else data
        response = self._send_with_retry(method, url, headers, payload)
        if is_sync_collection and response.status_code == 403 and _is_invalid_sync_token_error(response):
            raise CalDAVSyncTokenInvalidError(f'Sync token rejected (403) for {url}')
        _raise_for_status(response)
        return response

    def _send_with_retry(self, method, url, headers, payload):
        """Issue the request, retrying transient network failures with
        exponential backoff. Any failure that outlasts the retries - or that
        isn't retryable in the first place - is re-raised as a
        CalDAVConnectionError so callers only ever have to catch CalDAVError.
        """
        last_exc = None
        for attempt in range(RETRIES + 1):
            try:
                return self.session.request(
                    method, url, headers=headers, data=payload, timeout=self.timeout,
                )
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                last_exc = exc
                if attempt < RETRIES:
                    time.sleep(RETRY_BACKOFF * (2 ** attempt))
                    _logger.info(
                        'CalDAV: %s %s failed (%s), retrying (%d/%d)',
                        method, url, exc.__class__.__name__, attempt + 1, RETRIES,
                    )
                    continue
            except requests.exceptions.RequestException as exc:
                raise CalDAVConnectionError(f'{method} {url} failed: {exc}') from exc
        raise CalDAVConnectionError(
            f'{method} {url} still failing after {RETRIES + 1} attempts '
            f'(timeouts {self.timeout[0]}s/{self.timeout[1]}s): {last_exc}'
        ) from last_exc

    def _propfind(self, url, body, depth=0):
        response = self._request(
            'PROPFIND', url, depth=depth,
            headers={'Content-Type': 'application/xml; charset=utf-8'},
            data=body,
        )
        return etree.fromstring(response.content)

    # ------------------------------------------------------------------
    # Connectivity check
    # ------------------------------------------------------------------
    def test_connection(self):
        """Raises on failure; returns the collection displayname on success."""
        body = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<d:propfind xmlns:d="DAV:">'
            '<d:prop><d:displayname/><d:resourcetype/></d:prop>'
            '</d:propfind>'
        )
        root = self._propfind(self.calendar_url, body, depth=0)
        name = False
        for response in root.findall('d:response', NS):
            name = _text(response.find('.//d:displayname', NS))
        return name or self.calendar_url

    # ------------------------------------------------------------------
    # Discovery: principal -> calendar-home-set -> list of calendars
    # ------------------------------------------------------------------
    def discover_calendars(self):
        """Best-effort discovery starting from ``self.base_url``.

        Returns a list of dicts: {href, url, display_name, ctag}.
        """
        principal_href = self._discover_current_user_principal()
        home_set_href = self._discover_calendar_home_set(principal_href)
        return self._list_calendars(home_set_href)

    def _discover_current_user_principal(self):
        body = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<d:propfind xmlns:d="DAV:">'
            '<d:prop><d:current-user-principal/></d:prop>'
            '</d:propfind>'
        )
        for candidate in (self.calendar_url, urljoin(self.base_url, '/.well-known/caldav')):
            try:
                root = self._propfind(candidate, body, depth=0)
            except CalDAVError:
                continue
            href = _text(root.find('.//d:current-user-principal/d:href', NS))
            if href:
                return urljoin(self.base_url, href)
        raise CalDAVError('Could not discover current-user-principal on this server.')

    def _discover_calendar_home_set(self, principal_url):
        body = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">'
            '<d:prop><c:calendar-home-set/></d:prop>'
            '</d:propfind>'
        )
        root = self._propfind(principal_url, body, depth=0)
        href = _text(root.find('.//c:calendar-home-set/d:href', NS))
        if not href:
            raise CalDAVError('Could not discover calendar-home-set on this server.')
        return urljoin(self.base_url, href)

    def _list_calendars(self, home_set_url):
        body = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav" xmlns:cs="http://calendarserver.org/ns/">'
            '<d:prop>'
            '<d:resourcetype/><d:displayname/><cs:getctag/>'
            '<c:supported-calendar-component-set/>'
            '</d:prop>'
            '</d:propfind>'
        )
        root = self._propfind(home_set_url, body, depth=1)
        calendars = []
        for response in root.findall('d:response', NS):
            resourcetype = response.find('.//d:resourcetype', NS)
            if resourcetype is None or resourcetype.find('c:calendar', NS) is None:
                continue
            href = _text(response.find('d:href', NS))
            if not href:
                continue
            supports_events = True
            comp_set = response.find('.//c:supported-calendar-component-set', NS)
            if comp_set is not None:
                comps = [c.get('name') for c in comp_set.findall('c:comp', NS)]
                supports_events = not comps or 'VEVENT' in comps
            if not supports_events:
                continue
            calendars.append({
                'href': href,
                'url': urljoin(self.base_url, href),
                'display_name': _text(response.find('.//d:displayname', NS)) or href,
                'ctag': _find_ctag(response),
            })
        return calendars

    # ------------------------------------------------------------------
    # Incremental pull: RFC 6578 sync-collection, with ctag fallback
    # ------------------------------------------------------------------
    def get_ctag(self):
        body = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<d:propfind xmlns:d="DAV:" xmlns:cs="http://calendarserver.org/ns/">'
            '<d:prop><cs:getctag/></d:prop>'
            '</d:propfind>'
        )
        root = self._propfind(self.calendar_url, body, depth=0)
        return _find_ctag(root)

    def sync_collection(self, sync_token=None):
        """RFC 6578 incremental sync.

        Returns (changes, new_sync_token) where changes is a list of dicts
        {href, etag, deleted}. Raises CalDAVSyncTokenInvalidError if the
        server rejects the token (caller should do a full resync).
        """
        token_xml = f'<d:sync-token>{xml_escape(sync_token)}</d:sync-token>' if sync_token else '<d:sync-token/>'
        body = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<d:sync-collection xmlns:d="DAV:">'
            f'{token_xml}'
            '<d:sync-level>1</d:sync-level>'
            '<d:prop><d:getetag/></d:prop>'
            '</d:sync-collection>'
        )
        response = self._request(
            'REPORT', self.calendar_url,
            headers={'Content-Type': 'application/xml; charset=utf-8', 'Depth': '1'},
            data=body,
            is_sync_collection=True,
        )
        root = etree.fromstring(response.content)
        changes = []
        for resp in root.findall('d:response', NS):
            href = _text(resp.find('d:href', NS))
            status = _text(resp.find('d:status', NS)) or ''
            propstat_status = _text(resp.find('.//d:propstat/d:status', NS)) or ''
            deleted = '404' in status or '404' in propstat_status
            etag = _text(resp.find('.//d:getetag', NS))
            if href:
                changes.append({'href': urljoin(self.base_url, href), 'etag': etag, 'deleted': deleted})
        new_token = _text(root.find('d:sync-token', NS))
        return changes, new_token

    def list_all_events(self):
        """Fallback full listing via calendar-query, returns [{href, etag}]."""
        body = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">'
            '<d:prop><d:getetag/></d:prop>'
            '<c:filter><c:comp-filter name="VCALENDAR"><c:comp-filter name="VEVENT"/></c:comp-filter></c:filter>'
            '</c:calendar-query>'
        )
        response = self._request(
            'REPORT', self.calendar_url,
            headers={'Content-Type': 'application/xml; charset=utf-8', 'Depth': '1'},
            data=body,
        )
        root = etree.fromstring(response.content)
        events = []
        for resp in root.findall('d:response', NS):
            href = _text(resp.find('d:href', NS))
            etag = _text(resp.find('.//d:getetag', NS))
            if href:
                events.append({'href': urljoin(self.base_url, href), 'etag': etag})
        return events

    def multiget(self, hrefs):
        """Fetch etag + ics body for a batch of hrefs in one REPORT call."""
        if not hrefs:
            return []
        href_xml = ''.join(f'<d:href>{xml_escape(urlparse(h).path)}</d:href>' for h in hrefs)
        body = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<c:calendar-multiget xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">'
            '<d:prop><d:getetag/><c:calendar-data/></d:prop>'
            f'{href_xml}'
            '</c:calendar-multiget>'
        )
        response = self._request(
            'REPORT', self.calendar_url,
            headers={'Content-Type': 'application/xml; charset=utf-8', 'Depth': '1'},
            data=body,
        )
        root = etree.fromstring(response.content)
        results = []
        for resp in root.findall('d:response', NS):
            href = _text(resp.find('d:href', NS))
            etag = _text(resp.find('.//d:getetag', NS))
            data = _text(resp.find('.//c:calendar-data', NS))
            if href and data:
                results.append({'href': urljoin(self.base_url, href), 'etag': etag, 'ics': data})
        return results

    # ------------------------------------------------------------------
    # Push
    # ------------------------------------------------------------------
    def put_event(self, href_or_uid, ics_data, etag=None, create=False):
        """PUT an .ics resource. Returns the new ETag (may be False if the
        server doesn't return one, in which case the caller should re-fetch).
        """
        url = href_or_uid if href_or_uid.startswith('http') else urljoin(self.calendar_url, f'{href_or_uid}.ics')
        headers = {'Content-Type': 'text/calendar; charset=utf-8'}
        if create:
            headers['If-None-Match'] = '*'
        elif etag:
            headers['If-Match'] = etag
        response = self._request('PUT', url, headers=headers, data=ics_data)
        return url, response.headers.get('ETag') or False

    def delete_event(self, href, etag=None):
        headers = {}
        if etag:
            headers['If-Match'] = etag
        try:
            self._request('DELETE', href, headers=headers)
        except CalDAVNotFoundError:
            pass  # already gone remotely, nothing to do
