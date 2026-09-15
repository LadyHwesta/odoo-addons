# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import _, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _cart_find_product_line(self, *args, namecheap_domain_name=None, **kwargs):
        """Two different domains added through the same generic "Domain
        Registration" product must never merge into one line with
        quantity=2 - each is its own distinct thing being bought, unlike
        a normal product where quantity means "more of the same." Same
        pattern website_event_sale uses to keep different event tickets
        on the same product from merging.
        """
        lines = super()._cart_find_product_line(*args, **kwargs)
        if not namecheap_domain_name:
            return lines
        return lines.filtered(lambda line: line.namecheap_domain_name == namecheap_domain_name)

    def _prepare_order_line_values(
            self, product_id, quantity, uom_id, *,
            namecheap_domain_name=None, namecheap_years=None, **kwargs):
        values = super()._prepare_order_line_values(product_id, quantity, uom_id, **kwargs)
        if namecheap_domain_name:
            values['namecheap_domain_name'] = namecheap_domain_name
            values['namecheap_years'] = namecheap_years or 1
        return values

    def _action_confirm(self):
        result = super()._action_confirm()
        for order in self:
            order._namecheap_register_domain_lines()
        return result

    def _namecheap_register_domain_lines(self):
        """For every confirmed line selling a domain (namecheap_domain_name
        set - see the domain search page's add-to-cart action), actually
        register it at Namecheap and set up its yearly renewal billing.

        Mirrors hestiacp_hosting's own _hestiacp_provision_hosting_lines
        almost exactly - same trigger point (order confirmation, which a
        real website_sale checkout only reaches after payment succeeds),
        same contract-based recurring billing pattern. One real
        difference worth knowing: if this exact domain got registered by
        someone else between add-to-cart and checkout completing (a real
        if rare race condition - domains aren't reserved on add-to-cart),
        register_domain raises here, *after* the customer's already been
        charged. Not specially handled - the same class of risk
        hestiacp_hosting accepts for a username collision, just flagged
        explicitly since real money and a whole domain are at stake here.
        """
        self.ensure_one()
        for line in self.order_line.filtered(lambda line_: line_.namecheap_domain_name):
            template = line.product_id.product_tmpl_id
            server = template.namecheap_server_id
            if not server:
                raise UserError(_(
                    "%(product)s has no Namecheap account configured.",
                    product=template.name))

            domain_name = line.namecheap_domain_name
            sld, tld = domain_name.split('.', 1)
            years = line.namecheap_years or 1

            contact = self.partner_id._namecheap_registrant_fields()
            server.register_domain(sld, tld, years, contact)

            checkout_tx = self.get_portal_last_transaction()
            today = fields.Date.context_today(self)
            contract = self.env['contract.contract'].create({
                'name': f'{domain_name} - {self.partner_id.name}',
                'partner_id': self.partner_id.id,
                'pricelist_id': self.pricelist_id.id,
                'company_id': self.company_id.id,
                'contract_type': 'sale',
                'line_recurrence': True,
                'contract_line_ids': [(0, 0, {
                    'product_id': line.product_id.id,
                    'name': f'Domain renewal: {domain_name}',
                    'quantity': 1,
                    'price_unit': line.price_unit,
                    'date_start': today,
                    'recurring_interval': years,
                    'recurring_rule_type': 'yearly',
                    'recurring_invoicing_type': 'pre-paid',
                })],
            })
            self.env['namecheap.domain'].create({
                'name': domain_name,
                'server_id': server.id,
                'partner_id': self.partner_id.id,
                'sale_order_id': self.id,
                'contract_id': contract.id,
                'registered_on': today,
                'expires_on': today + relativedelta(years=years),
                'state': 'active',
                'payment_token_id': checkout_tx.token_id.id if checkout_tx else False,
            })
