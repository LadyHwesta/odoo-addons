# -*- coding: utf-8 -*-
import re

from odoo import http
from odoo.http import request

# A conservative subset of what's actually a legal domain label - just
# enough to reject garbage before it reaches Namecheap's own API (which
# has the real, authoritative validation). Requires at least one dot so
# a bare SLD with no TLD can't be searched.
DOMAIN_RE = re.compile(r'^(?!-)[a-z0-9-]{1,63}(?<!-)(\.[a-z0-9-]{1,63})+$')


class DomainSearch(http.Controller):

    @http.route('/domains', type='http', auth='public', website=True, sitemap=True)
    def domain_search_page(self, **kwargs):
        return request.render('namecheap_domains_sale.domain_search_page', {})

    def _get_registration_product(self):
        """The one "Domain Registration" product used as the generic
        carrier for every domain line - see product.template's own
        is_domain_registration field for why there's exactly one
        product template regardless of which TLD or domain a customer
        actually buys.
        """
        return request.env['product.template'].sudo().search(
            [('is_domain_registration', '=', True),
             ('namecheap_server_id', '!=', False)], limit=1)

    @http.route('/domains/search', type='jsonrpc', auth='public', website=True)
    def search(self, domain=''):
        """Check one domain's availability and sell price. Always
        re-verifies against Namecheap directly rather than trusting
        anything the page already showed - a search result can go
        stale (someone else registers it) between when it's shown and
        when the customer adds it to cart, so add_to_cart below
        re-checks again anyway; this endpoint exists for the
        page's own live search box.
        """
        domain = (domain or '').strip().lower()
        if not DOMAIN_RE.match(domain):
            return {'error': "That doesn't look like a valid domain name."}

        product = self._get_registration_product()
        if not product:
            return {'error': "Domain registration isn't available right now."}

        server = product.namecheap_server_id
        result = server.check_domain_availability([domain])[0]
        return {
            'domain': result['domain'],
            'available': result['available'],
            'premium': result['premium'],
            'price': result['sell_price'],
            'currency': request.website.currency_id.name,
        }

    @http.route('/domains/add_to_cart', type='jsonrpc', auth='public', website=True)
    def add_to_cart(self, domain='', years=1):
        """Add one domain to the cart at its real, freshly-verified
        price - the client never gets to say what a domain costs.

        sale.order.line.price_unit is a *computed* field
        (_compute_price_unit, store=True, readonly=False, precompute=True
        - same "computed default, editable afterward" pattern this
        project already relies on for contract.line.recurring_next_date),
        so writing it directly after _cart_add creates the line is a
        supported override, not a hack: nothing else re-triggers that
        compute on an existing line afterward.
        """
        domain = (domain or '').strip().lower()
        try:
            years = max(1, int(years))
        except (TypeError, ValueError):
            years = 1

        if not DOMAIN_RE.match(domain):
            return {'error': "That doesn't look like a valid domain name."}

        product = self._get_registration_product()
        if not product:
            return {'error': "Domain registration isn't available right now."}

        server = product.namecheap_server_id
        result = server.check_domain_availability([domain])[0]
        if not result['available']:
            return {'error': "%s is no longer available." % domain}
        if not result['sell_price']:
            return {'error': "%s doesn't have a price set up yet." % domain}

        order_sudo = request.cart or request.website._create_cart()
        values = order_sudo.with_context(skip_cart_verification=True)._cart_add(
            product_id=product.product_variant_id.id,
            quantity=1,
            namecheap_domain_name=domain,
            namecheap_years=years,
        )
        line = order_sudo.order_line.filtered(lambda l: l.id == values['line_id'])
        if line:
            line.price_unit = result['sell_price'] * years

        return {
            'line_id': values['line_id'],
            'cart_quantity': order_sudo.cart_quantity,
        }
