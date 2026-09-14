# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class NamecheapTldPrice(models.Model):
    """One TLD's cached cost from Namecheap's own price sheet
    (namecheap.users.getPricing), plus the sell price this business
    charges after the server's markup_percentage. Namecheap's own docs
    describe this sheet as large and slow-changing and recommend
    fetching it once and caching it rather than querying live per
    customer search - this table *is* that cache, refreshed by a daily
    cron (see data/ir_cron.xml), not read fresh from Namecheap on every
    domain search.

    USD only for now - Namecheap's pricing sheet is returned in one
    currency per account and multi-currency storefronts aren't in
    scope yet (see README).
    """
    _name = 'namecheap.tld.price'
    _description = 'Namecheap TLD Pricing (cached)'
    _rec_name = 'tld'
    _order = 'tld'

    server_id = fields.Many2one('namecheap.server', required=True, ondelete='cascade')
    tld = fields.Char(required=True, help='Without the leading dot, e.g. "com".')
    register_cost = fields.Float(string="Namecheap Cost (1yr register)")
    renew_cost = fields.Float(string="Namecheap Cost (1yr renew)")
    sell_register_price = fields.Float(
        string="Sell Price (register)", compute='_compute_sell_prices', store=True)
    sell_renew_price = fields.Float(
        string="Sell Price (renew)", compute='_compute_sell_prices', store=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('tld_server_uniq', 'unique(server_id, tld)',
         "There's already a cached price for this TLD on this server."),
    ]

    @api.depends('register_cost', 'renew_cost', 'server_id.markup_percentage')
    def _compute_sell_prices(self):
        for price in self:
            markup = 1 + (price.server_id.markup_percentage or 0.0) / 100.0
            price.sell_register_price = price.register_cost * markup
            price.sell_renew_price = price.renew_cost * markup

    @api.model
    def _sync_from_namecheap(self, server):
        """Refresh every TLD's cached cost from
        namecheap.users.getPricing (ProductType "DOMAINS" ->
        ProductCategory "register"/"renew" -> one Product per TLD ->
        a Price child per registration-length tier, of which only the
        1-year one is kept - not independently verified against a live
        call yet (see namecheap_api.py's own docstring for why); if the
        real response nests this differently, this is the method to
        fix once the first sandbox sync is run.
        """
        client = server._get_client()
        costs = {}  # tld -> {'register': x, 'renew': y}
        for category, key in (('register', 'register'), ('renew', 'renew')):
            result = client.call(
                'namecheap.users.getPricing',
                ProductType='DOMAINS', ProductCategory=category)
            for product_type in result.iter('ProductType'):
                for product_category in product_type.iter('ProductCategory'):
                    for product in product_category.iter('Product'):
                        tld = (product.get('Name') or '').lower()
                        if not tld:
                            continue
                        one_year = next(
                            (p for p in product.iter('Price') if p.get('Duration') == '1'),
                            None)
                        if one_year is None:
                            continue
                        price = float(
                            one_year.get('YourPrice')
                            or one_year.get('Price')
                            or one_year.get('RegularPrice') or 0.0)
                        costs.setdefault(tld, {})[key] = price

        existing = {p.tld: p for p in self.search([('server_id', '=', server.id)])}
        for tld, values in costs.items():
            vals = {
                'register_cost': values.get('register', 0.0),
                'renew_cost': values.get('renew', 0.0),
            }
            if tld in existing:
                existing[tld].write(vals)
            else:
                self.create({'server_id': server.id, 'tld': tld, **vals})
        _logger.info('Namecheap: synced pricing for %d TLDs', len(costs))

    @api.model
    def _cron_sync_pricing(self):
        for server in self.env['namecheap.server'].search([]):
            try:
                self._sync_from_namecheap(server)
            except Exception:
                _logger.exception('Namecheap: pricing sync failed for %s', server.name)
