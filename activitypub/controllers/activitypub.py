# -*- coding: utf-8 -*-
"""The ``/ap`` endpoints: actors, their collections, stored objects and
activities, and the inbox.

Phase 2 serves a populated, paged outbox and a real follower collection, and
the inbox verifies HTTP Signatures and handles Follow / Undo / Accept.
"""
import json
import logging
import math

from odoo import http
from odoo.http import request

from ..models.activitypub_object import federation_enabled
from ..models.activitypub_service import (
    build_ordered_collection,
    build_ordered_collection_page,
    wants_activitypub,
)

_logger = logging.getLogger(__name__)

AP_HEADERS = [
    ('Content-Type', 'application/activity+json; charset=utf-8'),
    ('Access-Control-Allow-Origin', '*'),
]

PAGE_SIZE = 20
OUTBOX_TYPES = ('Create', 'Update', 'Delete', 'Announce')
MAX_INBOX_BYTES = 1024 * 1024


class ActivityPubController(http.Controller):

    # ------------------------------------------------------------------
    def _get_actor(self, actor_id):
        if not federation_enabled(request.env):
            return None
        actor = request.env['activitypub.actor'].sudo().browse(actor_id).exists()
        if not actor or not actor.active:
            return None
        return actor

    def _json(self, doc):
        return request.make_json_response(doc, headers=AP_HEADERS)

    # ------------------------------------------------------------------
    # Actor object
    # ------------------------------------------------------------------
    @http.route('/ap/actors/<int:actor_id>', type='http', auth='public',
                methods=['GET'], website=True, sitemap=False, csrf=False)
    def actor(self, actor_id, **kw):
        actor = self._get_actor(actor_id)
        if not actor:
            raise request.not_found()
        if not wants_activitypub(request.httprequest.headers.get('Accept', '')):
            return request.redirect(actor._human_url(), code=302, local=False)
        return self._json(actor._ap_actor_document())

    @http.route('/ap/actors/<int:actor_id>/icon', type='http', auth='public',
                methods=['GET'], website=True, sitemap=False, csrf=False)
    def actor_icon(self, actor_id, **kw):
        """The actor's avatar bytes. Public and unauthenticated - a Fediverse
        server fetching it has no Odoo session and no model access, so
        ``/web/image`` would refuse it."""
        actor = self._get_actor(actor_id)
        data = actor and actor._icon_bytes()
        if not data:
            raise request.not_found()
        return request.make_response(data, headers=[
            ('Content-Type', (actor._icon_info() or {}).get('mediaType', 'image/png')),
            ('Content-Length', str(len(data))),
            ('Cache-Control', 'public, max-age=86400'),
            ('Access-Control-Allow-Origin', '*'),
        ])

    # ------------------------------------------------------------------
    # Outbox (paged OrderedCollection of published activities)
    # ------------------------------------------------------------------
    @http.route('/ap/actors/<int:actor_id>/outbox', type='http', auth='public',
                methods=['GET'], website=True, sitemap=False, csrf=False)
    def outbox(self, actor_id, page=None, **kw):
        actor = self._get_actor(actor_id)
        if not actor:
            raise request.not_found()
        Activity = request.env['activitypub.activity'].sudo()
        domain = [
            ('actor_id', '=', actor.id),
            ('direction', '=', 'out'),
            ('activity_type', 'in', list(OUTBOX_TYPES)),
            # Excludes actor-profile Updates (e.g. "Push Profile to
            # Followers"): those wrap the actor document, not a post, and
            # have no object_id. Without this a profile edit inflates the
            # outbox's totalItems, which is what some servers show as the
            # account's post count before they've ingested anything.
            ('object_id', '!=', False),
        ]
        total = Activity.search_count(domain)
        outbox_id = actor._endpoint('/outbox')

        if page is None:
            last_page = max(1, math.ceil(total / PAGE_SIZE))
            return self._json(build_ordered_collection(
                outbox_id, total,
                first=f'{outbox_id}?page=1',
                last=f'{outbox_id}?page={last_page}'))

        try:
            current = max(1, int(page))
        except (TypeError, ValueError):
            current = 1
        activities = Activity.search(
            domain, order='id desc',
            limit=PAGE_SIZE, offset=(current - 1) * PAGE_SIZE)
        items = [a.payload for a in activities if a.payload]
        has_next = current * PAGE_SIZE < total
        return self._json(build_ordered_collection_page(
            f'{outbox_id}?page={current}', outbox_id, items,
            next_url=f'{outbox_id}?page={current + 1}' if has_next else None,
            prev_url=f'{outbox_id}?page={current - 1}' if current > 1 else None))

    # ------------------------------------------------------------------
    # Followers / following
    # ------------------------------------------------------------------
    @http.route('/ap/actors/<int:actor_id>/followers', type='http', auth='public',
                methods=['GET'], website=True, sitemap=False, csrf=False)
    def followers(self, actor_id, page=None, **kw):
        actor = self._get_actor(actor_id)
        if not actor:
            raise request.not_found()
        Follower = request.env['activitypub.follower'].sudo()
        domain = [('actor_id', '=', actor.id), ('state', '=', 'accepted')]
        total = Follower.search_count(domain)
        coll_id = actor._endpoint('/followers')

        if page is None:
            last_page = max(1, math.ceil(total / PAGE_SIZE))
            return self._json(build_ordered_collection(
                coll_id, total,
                first=f'{coll_id}?page=1',
                last=f'{coll_id}?page={last_page}'))

        try:
            current = max(1, int(page))
        except (TypeError, ValueError):
            current = 1
        rows = Follower.search(domain, order='id',
                               limit=PAGE_SIZE, offset=(current - 1) * PAGE_SIZE)
        has_next = current * PAGE_SIZE < total
        return self._json(build_ordered_collection_page(
            f'{coll_id}?page={current}', coll_id, rows.mapped('follower_uri'),
            next_url=f'{coll_id}?page={current + 1}' if has_next else None,
            prev_url=f'{coll_id}?page={current - 1}' if current > 1 else None))

    @http.route('/ap/actors/<int:actor_id>/following', type='http', auth='public',
                methods=['GET'], website=True, sitemap=False, csrf=False)
    def following(self, actor_id, **kw):
        actor = self._get_actor(actor_id)
        if not actor:
            raise request.not_found()
        coll_id = actor._endpoint('/following')
        return self._json(build_ordered_collection(coll_id, 0))

    # ------------------------------------------------------------------
    # Stored objects and activities
    # ------------------------------------------------------------------
    @http.route('/ap/objects/<int:object_id>', type='http', auth='public',
                methods=['GET'], website=True, sitemap=False, csrf=False)
    def ap_object(self, object_id, **kw):
        if not federation_enabled(request.env):
            raise request.not_found()
        obj = request.env['activitypub.object'].sudo().browse(object_id).exists()
        if not obj or not obj.local or obj.deleted or not obj.payload:
            raise request.not_found()
        if not wants_activitypub(request.httprequest.headers.get('Accept', '')):
            return request.redirect(obj._human_url(), code=302, local=False)
        return self._json(obj.payload)

    @http.route('/ap/activities/<int:activity_id>', type='http', auth='public',
                methods=['GET'], website=True, sitemap=False, csrf=False)
    def ap_activity(self, activity_id, **kw):
        if not federation_enabled(request.env):
            raise request.not_found()
        activity = request.env['activitypub.activity'].sudo().browse(activity_id).exists()
        if not activity or activity.direction != 'out' or not activity.payload:
            raise request.not_found()
        return self._json(activity.payload)

    # ------------------------------------------------------------------
    # Inbox
    # ------------------------------------------------------------------
    @http.route(['/ap/actors/<int:actor_id>/inbox', '/ap/inbox'], type='http',
                auth='public', methods=['POST'], website=True, sitemap=False,
                csrf=False)
    def inbox(self, actor_id=None, **kw):
        if not federation_enabled(request.env):
            raise request.not_found()

        body = request.httprequest.get_data(cache=False)
        if len(body) > MAX_INBOX_BYTES:
            return request.make_response('', status=413)
        try:
            raw = json.loads(body)
            if not isinstance(raw, dict):
                raise ValueError('not a JSON object')
        except ValueError:
            return request.make_response('', status=400)

        target = None
        if actor_id is not None:
            target = self._get_actor(actor_id)
            if not target:
                raise request.not_found()

        headers = dict(request.httprequest.headers.items())
        # The sender signed (request-target) as the bare path, no query string.
        path = request.httprequest.path
        status = request.env['activitypub.activity'].sudo()._ingest(
            raw, headers, path, body, target)
        return request.make_response('', status=status)
