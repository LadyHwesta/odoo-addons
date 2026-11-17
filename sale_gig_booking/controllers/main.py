# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


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
        """The sales team booking requests from this website go to, in the
        website's own company: its lead team (set in the form editor) when
        that's in the same company, else its shop orders team (eCommerce >
        Orders Assignment). Without this, a website belonging to another
        company than the default lead team refused every request (found
        live on djembass.com, 2026-11-16)."""
        website = request.website.sudo()
        company = website.company_id
        for team in (website.crm_default_team_id, getattr(website, 'salesteam_id', None)):
            if team and (not team.company_id or team.company_id == company):
                return team
        return request.env['crm.team'].sudo().search([
            ('company_id', 'in', [company.id, False]), ('use_opportunities', '=', True)], limit=1)

