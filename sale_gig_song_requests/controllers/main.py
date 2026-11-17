# -*- coding: utf-8 -*-
import hashlib
from datetime import timedelta

from odoo import _, fields, http
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal

GUEST_LIMIT = 5            # requests per phone...
GUEST_WINDOW_MINUTES = 10  # ...in this many minutes
GIG_LIMIT = 500            # requests per gig in all
CLIENT_LIMIT = 200         # songs on the client's lists


def _clean(value, size):
    return ' '.join((value or '').split())[:size]


class SongRequests(http.Controller):

    def _gig(self, token):
        if not token or len(token) > 64:
            return request.env['sale.order']
        return request.env['sale.order'].sudo().search(
            [('song_request_token', '=', token), ('is_gig', '=', True)], limit=1)

    def _requester_key(self, order):
        ip = request.httprequest.remote_addr or ''
        return hashlib.sha256(f'{order.id}:{ip}'.encode()).hexdigest()[:16]

    @http.route('/gig/<string:token>/songs', type='http', auth='public', website=True,
                methods=['GET', 'POST'], sitemap=False)
    def song_request_page(self, token, **post):
        order = self._gig(token)
        if not order:
            raise request.not_found()
        values = {'order': order, 'token': token, 'open': order._song_requests_open(),
                  'sent': bool(post.get('sent')), 'error': False}
        if request.httprequest.method == 'POST' and values['open']:
            values['error'] = self._take_request(order, post)
            if not values['error']:
                return request.redirect(f'/gig/{token}/songs?sent=1')
            values['form'] = post
        return request.render('sale_gig_song_requests.song_request_page', values)

    def _take_request(self, order, post):
        """Store a guest's request; an error message if it can't be taken."""
        if post.get('website_url'):  # filled only by bots: the field is hidden
            return False
        song = _clean(post.get('song'), 120)
        if not song:
            return _("Which song would you like?")
        try:
            request.env['ir.http']._verify_request_recaptcha_token('song_request')
        except (UserError, ValidationError):
            return _("We couldn't check that you're not a robot. Please try again.")
        Request = request.env['gig.song.request'].sudo()
        key = self._requester_key(order)
        since = fields.Datetime.now() - timedelta(minutes=GUEST_WINDOW_MINUTES)
        if Request.search_count([('order_id', '=', order.id), ('requester_key', '=', key),
                                 ('create_date', '>=', since)]) >= GUEST_LIMIT:
            return _("You've sent a few already. Give the DJ a little while, then ask again.")
        if Request.search_count([('order_id', '=', order.id), ('kind', '=', 'request')]) >= GIG_LIMIT:
            return _("The request list is full for tonight.")
        Request.create({
            'order_id': order.id, 'kind': 'request', 'song': song,
            'artist': _clean(post.get('artist'), 120), 'requested_by': _clean(post.get('name'), 60),
            'requester_key': key,
        })
        return False


class SongListPortal(CustomerPortal):

    @http.route('/my/orders/<int:order_id>/music', type='http', auth='public', website=True,
                methods=['GET', 'POST'], sitemap=False)
    def portal_music(self, order_id, access_token=None, **post):
        try:
            order = self._document_check_access('sale.order', order_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')
        if not order.is_gig:
            return request.redirect(order.get_portal_url())
        is_open = order._song_lists_open()
        error = False
        if request.httprequest.method == 'POST':
            if not is_open:
                error = _("Your lists are locked now that the gig has started.")
            else:
                error = self._change_lists(order, post)
            if not error:
                query = f'?access_token={access_token}' if access_token else ''
                return request.redirect(f'/my/orders/{order.id}/music{query}')
        return request.render('sale_gig_song_requests.portal_music_page', {
            'order': order, 'access_token': access_token, 'open': is_open, 'error': error,
            'must': order.song_must_ids, 'never': order.song_never_ids,
            'page_name': 'music',
        })

    def _change_lists(self, order, post):
        Request = request.env['gig.song.request'].sudo()
        if post.get('remove'):
            line = Request.browse(int(post['remove'])).exists() if post['remove'].isdigit() else Request
            if line and line.order_id == order and line.kind in ('must_play', 'do_not_play'):
                line.unlink()
            return False
        kind = post.get('kind')
        song = _clean(post.get('song'), 120)
        if kind not in ('must_play', 'do_not_play') or not song:
            return _("Add a song title.")
        if len(order.song_must_ids) + len(order.song_never_ids) >= CLIENT_LIMIT:
            return _("Your lists are full. Remove a song to add another.")
        Request.create({
            'order_id': order.id, 'kind': kind, 'song': song,
            'artist': _clean(post.get('artist'), 120), 'note': _clean(post.get('note'), 80),
            'requested_by': order.partner_id.name,
        })
        return False
