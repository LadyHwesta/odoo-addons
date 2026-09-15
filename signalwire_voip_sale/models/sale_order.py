# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError

# One generic product represents the metered-usage line on every
# customer's contract, regardless of which number(s) they have - its
# own list_price is never actually charged (the line's real price_unit
# gets computed fresh each period, see contract.line's own override),
# it exists only so the line has *some* product/account to post
# against, the same role namecheap_domains_sale's own generic
# "Domain Registration" product plays for domain lines.
USAGE_PRODUCT_XML_ID = 'signalwire_voip_sale.product_signalwire_usage'


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _cart_find_product_line(self, *args, signalwire_phone_number=None, **kwargs):
        """Two different numbers added through the same generic "VoIP
        Number" product must never merge into one line with quantity
        2 - each number is its own distinct thing being bought, same
        reasoning (and same override pattern, from website_event_sale)
        as namecheap_domains_sale's own override for domain lines.
        """
        lines = super()._cart_find_product_line(*args, **kwargs)
        if not signalwire_phone_number:
            return lines
        return lines.filtered(
            lambda line: line.signalwire_phone_number == signalwire_phone_number)

    def _prepare_order_line_values(
            self, product_id, quantity, uom_id, *,
            signalwire_phone_number=None, **kwargs):
        values = super()._prepare_order_line_values(product_id, quantity, uom_id, **kwargs)
        if signalwire_phone_number:
            values['signalwire_phone_number'] = signalwire_phone_number
        return values

    def _action_confirm(self):
        result = super()._action_confirm()
        for order in self:
            order._signalwire_provision_number_lines()
        return result

    def _signalwire_provision_number_lines(self):
        """For every confirmed line selling a VoIP number
        (signalwire_phone_number set - see the VoIP search page's
        add-to-cart action), provision it for real: a subproject (new,
        or the customer's existing one), the purchased number itself,
        a customer SMS access token, and the two-line contract (flat
        rental + metered usage) that bills it going forward.

        Mirrors namecheap_domains_sale's own
        _namecheap_register_domain_lines almost exactly - same trigger
        point, same real-money-after-payment race risk if this exact
        number gets bought by someone else between add-to-cart and
        checkout completing (rare - numbers aren't reserved on add-to-
        cart, same as domains), not specially handled here either.
        """
        self.ensure_one()
        for line in self.order_line.filtered(lambda l: l.signalwire_phone_number):
            template = line.product_id.product_tmpl_id
            server = template.signalwire_server_id
            if not server:
                raise UserError(_(
                    "%(product)s has no SignalWire account configured.",
                    product=template.name))

            subproject = self.env['signalwire.subproject'].search([
                ('server_id', '=', server.id),
                ('partner_id', '=', self.partner_id.id),
                ('state', '=', 'active'),
            ], limit=1)
            if not subproject:
                subproject = self.env['signalwire.subproject'].create({
                    'name': f'{self.partner_id.name} VoIP',
                    'server_id': server.id,
                    'partner_id': self.partner_id.id,
                })
                subproject.action_provision()

            number = subproject.purchase_number(line.signalwire_phone_number)
            subproject.action_issue_customer_token()

            today = fields.Date.context_today(self)
            usage_product = self.env.ref(USAGE_PRODUCT_XML_ID)
            self.env['contract.contract'].create({
                'name': f'{number.name} - {self.partner_id.name}',
                'partner_id': self.partner_id.id,
                'pricelist_id': self.pricelist_id.id,
                'company_id': self.company_id.id,
                'contract_type': 'sale',
                'line_recurrence': True,
                'contract_line_ids': [
                    (0, 0, {
                        'product_id': line.product_id.id,
                        'name': f'{number.name} - monthly number rental',
                        'quantity': 1,
                        'price_unit': line.price_unit,
                        'date_start': today,
                        'recurring_interval': 1,
                        'recurring_rule_type': 'monthly',
                        'recurring_invoicing_type': 'pre-paid',
                    }),
                    (0, 0, {
                        'product_id': usage_product.id,
                        'name': f'{number.name} - metered usage',
                        'quantity': 1,
                        'price_unit': 0.0,
                        'date_start': today,
                        'recurring_interval': 1,
                        'recurring_rule_type': 'monthly',
                        'recurring_invoicing_type': 'post-paid',
                        'is_signalwire_metered': True,
                        'signalwire_subproject_id': subproject.id,
                    }),
                ],
            })
