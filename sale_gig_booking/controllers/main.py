# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class GigBookingController(http.Controller):

    @http.route('/book', type='http', auth='public', website=True, sitemap=True)
    def book(self, **kwargs):
        """The booking request form: a normal website form that creates a
        lead (with Turnstile/reCAPTCHA, like any other website form)."""
        return request.render('sale_gig_booking.book_page', {
            'gig_types': request.env['crm.lead']._fields['gig_type'].selection,
            'gig_settings': request.env['crm.lead']._fields['gig_setting'].selection,
            'hours': [(h / 2, '%d:%02d %s' % ((h // 2) % 12 or 12, (h % 2) * 30, 'am' if h < 24 else 'pm'))
                      for h in range(0, 48)],
        })

    @http.route('/book/thank-you', type='http', auth='public', website=True, sitemap=False)
    def book_thanks(self, **kwargs):
        return request.render('sale_gig_booking.book_thanks_page')
