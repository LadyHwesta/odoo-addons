# -*- coding: utf-8 -*-
"""The ``/ap`` endpoints: the Actor object and its collections, plus a
placeholder inbox.

Phase 1 serves the Actor document (so a handle resolves from a Mastodon
search) and empty outbox / followers / following collections. Follower
handling, a populated outbox and real inbox processing arrive with the
bridge modules.
"""
import logging

from odoo import http
from odoo.http import request

from ..models.activitypub_service import (
    build_ordered_collection,
    wants_activitypub,
)
from .well_known import federation_enabled

_logger = logging.getLogger(__name__)

AP_HEADERS = [
    ('Content-Type', 'application/activity+json; charset=utf-8'),
    ('Access-Control-Allow-Origin', '*'),
]


class ActivityPubController(http.Controller):

    def _get_actor(self, actor_id):
        if not federation_enabled(request.env):
            return None
        actor = request.env['activitypub.actor'].sudo().browse(actor_id).exists()
        if not actor or not actor.active:
            return None
        return actor

    @http.route('/ap/actors/<int:actor_id>', type='http', auth='public',
                methods=['GET'], website=True, sitemap=False, csrf=False)
    def actor(self, actor_id, **kw):
        actor = self._get_actor(actor_id)
        if not actor:
            raise request.not_found()
        if not wants_activitypub(request.httprequest.headers.get('Accept', '')):
            # A browser landed here - send it to the website.
            return request.redirect(actor._human_url(), code=302, local=False)
        return request.make_json_response(actor._ap_actor_document(), headers=AP_HEADERS)

    @http.route('/ap/actors/<int:actor_id>/outbox', type='http', auth='public',
                methods=['GET'], website=True, sitemap=False, csrf=False)
    def outbox(self, actor_id, **kw):
        actor = self._get_actor(actor_id)
        if not actor:
            raise request.not_found()
        outbox_id = actor._endpoint('/outbox')
        return request.make_json_response(
            build_ordered_collection(outbox_id, 0, first=f'{outbox_id}?page=1'),
            headers=AP_HEADERS)

    @http.route('/ap/actors/<int:actor_id>/followers', type='http', auth='public',
                methods=['GET'], website=True, sitemap=False, csrf=False)
    def followers(self, actor_id, **kw):
        actor = self._get_actor(actor_id)
        if not actor:
            raise request.not_found()
        coll_id = actor._endpoint('/followers')
        return request.make_json_response(
            build_ordered_collection(coll_id, 0), headers=AP_HEADERS)

    @http.route('/ap/actors/<int:actor_id>/following', type='http', auth='public',
                methods=['GET'], website=True, sitemap=False, csrf=False)
    def following(self, actor_id, **kw):
        actor = self._get_actor(actor_id)
        if not actor:
            raise request.not_found()
        coll_id = actor._endpoint('/following')
        return request.make_json_response(
            build_ordered_collection(coll_id, 0), headers=AP_HEADERS)

    @http.route(['/ap/actors/<int:actor_id>/inbox', '/ap/inbox'], type='http',
                auth='public', methods=['POST'], website=True, sitemap=False,
                csrf=False)
    def inbox(self, actor_id=None, **kw):
        # Phase 2 verifies the HTTP Signature and dispatches Follow / Undo /
        # Create / Like / Announce / Delete. For now the request is absorbed
        # so a probing server does not retry against a 404.
        _logger.info('ActivityPub inbox hit (actor_id=%s), not yet processed', actor_id)
        return request.make_response('', status=202)
