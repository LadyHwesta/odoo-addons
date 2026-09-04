# -*- coding: utf-8 -*-
"""Discovery endpoints: WebFinger and NodeInfo.

These live at fixed well-known paths (RFC 7033, RFC 8615) rather than under
``/ap``. They are ``website=True`` so ``request.website`` resolves to the
branch whose domain the request came in on - which is what scopes a
WebFinger lookup to the right set of actors.
"""
import logging

from odoo import http
from odoo.http import request

from ..models.activitypub_service import build_webfinger

_logger = logging.getLogger(__name__)

JRD_HEADERS = [
    ('Content-Type', 'application/jrd+json; charset=utf-8'),
    ('Access-Control-Allow-Origin', '*'),
]
JSON_CORS = [('Access-Control-Allow-Origin', '*')]


def federation_enabled(env):
    return env['ir.config_parameter'].sudo().get_param(
        'activitypub.enabled') in ('True', 'true', '1')


class ActivityPubWellKnown(http.Controller):

    @http.route('/.well-known/webfinger', type='http', auth='public',
                methods=['GET'], website=True, sitemap=False, csrf=False)
    def webfinger(self, resource=None, **kw):
        env = request.env
        if not federation_enabled(env):
            raise request.not_found()
        if not resource or not resource.startswith('acct:'):
            return request.make_json_response(
                {'error': 'the "resource" parameter must be an acct: URI'},
                status=400)
        username, _sep, want_host = resource[len('acct:'):].partition('@')
        actor = env['activitypub.actor'].sudo().search([
            ('username', '=', (username or '').lower()),
            ('website_id', '=', request.website.id),
            ('active', '=', True),
        ], limit=1)
        if not actor or not actor.actor_url:
            raise request.not_found()
        if want_host and want_host.lower() != (actor.domain or '').lower():
            raise request.not_found()
        return request.make_json_response(
            build_webfinger(actor.username, actor.domain, actor.actor_url),
            headers=JRD_HEADERS)

    @http.route('/.well-known/nodeinfo', type='http', auth='public',
                methods=['GET'], website=True, sitemap=False, csrf=False)
    def nodeinfo_index(self, **kw):
        base = request.httprequest.url_root.rstrip('/')
        return request.make_json_response({
            'links': [{
                'rel': 'http://nodeinfo.diaspora.software/ns/schema/2.1',
                'href': f'{base}/nodeinfo/2.1',
            }],
        }, headers=JSON_CORS)

    @http.route('/nodeinfo/2.1', type='http', auth='public',
                methods=['GET'], website=True, sitemap=False, csrf=False)
    def nodeinfo(self, **kw):
        env = request.env
        actors = env['activitypub.actor'].sudo().search_count([('active', '=', True)])
        return request.make_json_response({
            'version': '2.1',
            'software': {'name': 'odoo-activitypub', 'version': '19.0.1.0.0'},
            'protocols': ['activitypub'],
            'services': {'inbound': [], 'outbound': []},
            'openRegistrations': False,
            'usage': {'users': {'total': actors}, 'localPosts': 0},
            'metadata': {'nodeName': request.website.name or 'Odoo'},
        }, headers=JSON_CORS)
