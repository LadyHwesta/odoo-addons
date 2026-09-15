# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class VoipSearch(http.Controller):

    def _get_number_product(self):
        """The one "VoIP Number" product used as the generic carrier
        for every number a customer buys - see product.template's own
        is_voip_number field for why there's normally exactly one.
        """
        return request.env['product.template'].sudo().search(
            [('is_voip_number', '=', True),
             ('signalwire_server_id', '!=', False)], limit=1)

    @http.route('/voip', type='http', auth='public', website=True, sitemap=True)
    def voip_search_page(self, **kwargs):
        return request.render('signalwire_voip_sale.voip_search_page', {})

    @http.route('/voip/search', type='jsonrpc', auth='public', website=True)
    def search(self, area_code=''):
        """Search available numbers by area code - free, nothing
        reserved by looking. Unlike namecheap_domains_sale's own
        search, SignalWire has no per-number "is this one still free"
        check to re-run at add-to-cart time (AvailablePhoneNumbers is
        search-by-area-code only), so the real, authoritative check
        for a specific number happens where it has to: the actual
        purchase call at checkout - see sale_order.py's own docstring
        for the resulting (rare, accepted) race window.
        """
        product = self._get_number_product()
        if not product:
            return {'error': "VoIP numbers aren't available right now."}

        server = product.signalwire_server_id
        try:
            numbers = server.search_available_numbers(
                server.project_id, 'US', area_code=area_code or None)
        except Exception:
            return {'error': "Could not search for numbers right now - try again shortly."}

        return {
            'numbers': numbers,
            'price': product.list_price,
            'currency': request.website.currency_id.name,
        }

    @http.route('/voip/add_to_cart', type='jsonrpc', auth='public', website=True)
    def add_to_cart(self, phone_number=''):
        phone_number = (phone_number or '').strip()
        if not phone_number:
            return {'error': "Choose a number first."}

        product = self._get_number_product()
        if not product:
            return {'error': "VoIP numbers aren't available right now."}

        order_sudo = request.cart or request.website._create_cart()
        values = order_sudo.with_context(skip_cart_verification=True)._cart_add(
            product_id=product.product_variant_id.id,
            quantity=1,
            signalwire_phone_number=phone_number,
        )
        return {
            'line_id': values['line_id'],
            'cart_quantity': order_sudo.cart_quantity,
        }
