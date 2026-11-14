# -*- coding: utf-8 -*-
import re

from odoo import http
from odoo.http import request
from werkzeug.exceptions import NotFound

EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


class OnlineBooking(http.Controller):

    def _types(self):
        return request.env['resource.booking.type'].sudo().search(
            [('online_booking', '=', True), ('online_organizer_id', '!=', False)])

    @http.route('/book', type='http', auth='public', website=True, sitemap=True)
    def book_index(self, **kwargs):
        types = self._types()
        if len(types) == 1:
            return request.redirect(f'/book/{types.id}')
        return request.render('resource_booking_online.book_index', {'types': types})

    @http.route('/book/<int:type_id>', type='http', auth='public', website=True,
                sitemap=False, methods=['GET', 'POST'])
    def book_type(self, type_id, **post):
        """Name and email, then OCA's own page to pick a free time."""
        booking_type = self._types().filtered(lambda t: t.id == type_id)
        if not booking_type:
            raise NotFound()
        values = {'type': booking_type, 'error': None,
                  'name': (post.get('name') or '').strip(),
                  'email': (post.get('email') or '').strip(),
                  'phone': (post.get('phone') or '').strip()}
        if request.httprequest.method == 'POST':
            if post.get('website'):  # a field people can't see: only bots fill it
                raise NotFound()
            if not values['name'] or not EMAIL_RE.match(values['email']):
                values['error'] = request.env._("Please enter your name and a valid email.")
            else:
                booking = self._create_booking(booking_type, values)
                token = booking._portal_ensure_token()
                return request.redirect(
                    f'/my/bookings/{booking.id}/schedule?access_token={token}')
        return request.render('resource_booking_online.book_type', values)

    def _create_booking(self, booking_type, values):
        Partner = request.env['res.partner'].sudo()
        partner = Partner.search([('email', '=ilike', values['email'])], limit=1)
        if not partner:
            partner = Partner.create({'name': values['name'][:100], 'email': values['email'][:254],
                                      'phone': values['phone'][:40] or False})
        return request.env['resource.booking'].with_user(
            booking_type.online_organizer_id).sudo().create({
                'type_id': booking_type.id,
                'partner_ids': [(6, 0, [partner.id])],
                'user_id': booking_type.online_organizer_id.id,
            })
