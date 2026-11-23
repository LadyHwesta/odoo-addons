# -*- coding: utf-8 -*-
import re

from odoo import _, http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal

TIMELINE_LIMIT = 60


class GigBookingController(http.Controller):

    @http.route('/book', type='http', auth='public', website=True, sitemap=True)
    def book(self, **kwargs):
        """The booking request form: a normal website form that creates a
        lead (with Turnstile/reCAPTCHA, like any other website form)."""
        return request.render('sale_gig_booking.book_page', {
            'team': self._booking_team(),
            'gig_types': request.env['crm.lead']._fields['gig_type'].selection,
            'gig_settings': request.env['crm.lead']._fields['gig_setting'].selection,
            'hours': [(h / 2, '%d:%02d %s' % ((h // 2) % 12 or 12, (h % 2) * 30, 'am' if h < 24 else 'pm'))
                      for h in range(0, 48)],
        })

    @http.route('/book/thank-you', type='http', auth='public', website=True, sitemap=False)
    def book_thanks(self, **kwargs):
        return request.render('sale_gig_booking.book_thanks_page')

    def _booking_team(self):
        """The sales team booking requests from this website go to: the one
        chosen in Website Settings (Booking Requests Go To), else, in the
        website's own company, its lead team (set in the form editor) when
        that's in the same company, else its shop orders team (eCommerce >
        Orders Assignment). Without this, a website belonging to another
        company than the default lead team refused every request (found
        live on djembass.com, 2026-11-16)."""
        website = request.website.sudo()
        if website.gig_booking_team_id:
            return website.gig_booking_team_id
        company = website.company_id
        for team in (website.crm_default_team_id, getattr(website, 'salesteam_id', None)):
            if team and (not team.company_id or team.company_id == company):
                return team
        return request.env['crm.team'].sudo().search([
            ('company_id', 'in', [company.id, False]), ('use_opportunities', '=', True)], limit=1)



class GigTimelinePortal(CustomerPortal):
    """The client's own event timeline, from their order in the portal,
    until the gig starts."""

    @http.route('/my/orders/<int:order_id>/timeline', type='http', auth='public', website=True,
                methods=['GET', 'POST'], sitemap=False)
    def portal_timeline(self, order_id, access_token=None, **post):
        try:
            order = self._document_check_access('sale.order', order_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')
        if not order.is_gig:
            return request.redirect(order.get_portal_url())
        is_open = order._gig_client_edit_open()
        error = False
        if request.httprequest.method == 'POST':
            error = self._change_timeline(order, post) if is_open else _(
                "Your timeline is locked now that the event has started.")
            if not error:
                query = f'?access_token={access_token}' if access_token else ''
                return request.redirect(f'/my/orders/{order.id}/timeline{query}')
        return request.render('sale_gig_booking.portal_timeline_page', {
            'order': order, 'access_token': access_token, 'open': is_open, 'error': error,
            'lines': order.gig_timeline_ids, 'page_name': 'gig_timeline',
        })

    def _change_timeline(self, order, post):
        Line = request.env['gig.timeline.line'].sudo()
        if post.get('remove'):
            line = Line.browse(int(post['remove'])).exists() if post['remove'].isdigit() else Line
            if line and line.order_id == order:
                line.unlink()
            return False
        match = re.fullmatch(r'(\d{1,2}):(\d{2})', (post.get('time') or '').strip())
        moment = ' '.join((post.get('moment') or '').split())[:80]
        if not match or int(match[1]) > 23 or int(match[2]) > 59 or not moment:
            return _("Add a time and what happens then.")
        if len(order.gig_timeline_ids) >= TIMELINE_LIMIT:
            return _("Your timeline is full. Remove a moment to add another.")
        Line.create({
            'order_id': order.id, 'hour': int(match[1]) + int(match[2]) / 60, 'moment': moment,
            'note': ' '.join((post.get('note') or '').split())[:120], 'added_by_client': True,
        })
        return False
