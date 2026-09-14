# -*- coding: utf-8 -*-
from markupsafe import Markup
from werkzeug.urls import url_encode

from odoo import _, fields, http
from odoo.http import request

from odoo.addons.website_sale.controllers.main import WebsiteSale


class WebsiteSale(WebsiteSale):
    """Blocks a hosting order's payment page behind an explicit,
    server-recorded acceptance of the Hosting Service Agreement -
    reusing website_sale's own ``_get_shop_payment_errors`` extension
    point (the same mechanism core uses to block payment when there's no
    shipping method available) rather than a client-side-only checkbox,
    so it can't be bypassed by skipping JS, and there's a real
    timestamp/IP/agreement-version on the order afterwards. See
    ``sale_order._hestiacp_requires_aup_acceptance``.
    """

    def _get_shop_payment_errors(self, order):
        errors = super()._get_shop_payment_errors(order)
        if order._hestiacp_requires_aup_acceptance() and not order.hestiacp_aup_accepted_on:
            accept_url = '/hosting/agreement?%s' % url_encode({'redirect': '/shop/payment'})
            errors.append((
                _("Please accept the Hosting Service Agreement"),
                Markup('%s <a href="%s">%s</a>') % (
                    _("Before paying for a hosting service, please read and accept the:"),
                    accept_url,
                    _("Hosting Service Agreement"),
                ),
            ))
        return errors

    @http.route('/hosting/agreement', type='http', auth='public', website=True, sitemap=False)
    def hestiacp_agreement(self, redirect=None, **kwargs):
        agreement = request.env['hestiacp.agreement'].sudo()._get_active()
        return request.render('hestiacp_hosting.hestiacp_agreement_page', {
            'agreement': agreement,
            'redirect': redirect or '/shop/payment',
        })

    @http.route('/hosting/agreement/accept', type='http', auth='public',
                website=True, sitemap=False, methods=['POST'])
    def hestiacp_agreement_accept(self, redirect=None, **kwargs):
        order_sudo = request.cart
        agreement = request.env['hestiacp.agreement'].sudo()._get_active()
        if order_sudo and agreement and kwargs.get('accept'):
            order_sudo.write({
                'hestiacp_aup_agreement_id': agreement.id,
                'hestiacp_aup_accepted_on': fields.Datetime.now(),
                'hestiacp_aup_accepted_ip': request.httprequest.remote_addr,
            })
        return request.redirect(redirect or '/shop/payment')
