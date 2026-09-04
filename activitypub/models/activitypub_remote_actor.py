# -*- coding: utf-8 -*-
import logging
from urllib.parse import urlparse

from odoo import api, fields, models

from .activitypub_service import fetch_json

_logger = logging.getLogger(__name__)

# How long a cached remote actor (and its public key) is trusted before we
# re-fetch. Long enough to keep inbox processing cheap, short enough that a
# key rotation on the other end is picked up within a day.
CACHE_TTL_HOURS = 24


class ActivityPubRemoteActor(models.Model):
    """A dereferenced remote actor, cached so that verifying a burst of
    inbound activity from the same server does not mean an HTTP round trip
    per request."""
    _name = 'activitypub.remote.actor'
    _description = 'Cached Remote ActivityPub Actor'
    _rec_name = 'uri'

    uri = fields.Char(required=True, index=True)
    inbox_url = fields.Char()
    shared_inbox_url = fields.Char()
    public_key_pem = fields.Text()
    key_id = fields.Char()
    preferred_username = fields.Char()
    domain = fields.Char()
    fetched_at = fields.Datetime()
    raw = fields.Json()

    _uri_uniq = models.Constraint('unique(uri)', 'This remote actor is already cached.')

    def _is_fresh(self):
        self.ensure_one()
        if not self.fetched_at:
            return False
        age = fields.Datetime.now() - self.fetched_at
        return age.total_seconds() < CACHE_TTL_HOURS * 3600

    @api.model
    def _get(self, uri, force_refresh=False):
        """Return the cached record for ``uri``, fetching / refreshing it when
        missing or stale. Raises :class:`RemoteFetchError` if the fetch fails
        and nothing usable is cached."""
        record = self.search([('uri', '=', uri)], limit=1)
        if record and record._is_fresh() and not force_refresh:
            return record
        try:
            doc = fetch_json(uri)
        except Exception:
            if record:
                _logger.warning('Refresh of remote actor %s failed; using stale cache', uri)
                return record
            raise
        vals = self._vals_from_document(uri, doc)
        if record:
            record.write(vals)
        else:
            record = self.create(vals)
        return record

    @api.model
    def _vals_from_document(self, uri, doc):
        public_key = doc.get('publicKey') or {}
        endpoints = doc.get('endpoints') or {}
        resolved_id = doc.get('id') or uri
        return {
            'uri': resolved_id,
            'inbox_url': doc.get('inbox'),
            'shared_inbox_url': endpoints.get('sharedInbox'),
            'public_key_pem': public_key.get('publicKeyPem'),
            'key_id': public_key.get('id'),
            'preferred_username': doc.get('preferredUsername'),
            'domain': urlparse(resolved_id).hostname,
            'fetched_at': fields.Datetime.now(),
            'raw': doc,
        }
