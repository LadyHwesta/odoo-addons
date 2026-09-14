# -*- coding: utf-8 -*-
from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    hestiacp_aup_agreement_id = fields.Many2one(
        'hestiacp.agreement', string="Hosting Agreement Accepted", readonly=True,
        help="Which version of the Hosting Service Agreement was accepted "
             "for this order, and when/from where - see "
             "hestiacp.agreement.version. Set by the checkout's own "
             "agreement page (controllers/agreement.py), not editable by "
             "hand, so it stays real evidence of what the customer saw.")
    hestiacp_aup_accepted_on = fields.Datetime(readonly=True)
    hestiacp_aup_accepted_ip = fields.Char(readonly=True)

    def _hestiacp_requires_aup_acceptance(self):
        """Whether this order needs the customer to accept the Hosting
        Service Agreement before it can be paid for - true whenever it
        sells at least one hosting package, regardless of what else is
        on it.
        """
        self.ensure_one()
        return bool(self.order_line.filtered(
            lambda line: line.product_id.product_tmpl_id.is_hosting_package))

    def _action_confirm(self):
        result = super()._action_confirm()
        for order in self:
            order._hestiacp_provision_hosting_lines()
        return result

    def _hestiacp_provision_hosting_lines(self):
        """For every confirmed line selling a hosting package, create the
        recurring billing contract plus the HestiaCP account, and
        provision it immediately.

        A real production checkout only reaches order confirmation after
        payment succeeds (website_sale's own flow), so "order confirmed"
        is the right trigger here - there's no separate "first invoice
        paid" event to wait for.
        """
        self.ensure_one()
        for line in self.order_line.filtered(
                lambda line_: line_.product_id.product_tmpl_id.is_hosting_package):
            template = line.product_id.product_tmpl_id
            contract = self.env['contract.contract'].create({
                'name': f'{template.name} - {self.partner_id.name}',
                'partner_id': self.partner_id.id,
                'pricelist_id': self.pricelist_id.id,
                'company_id': self.company_id.id,
                'contract_type': 'sale',
                'line_recurrence': True,
                'contract_line_ids': [(0, 0, {
                    'product_id': line.product_id.id,
                    'name': line.name,
                    'quantity': line.product_uom_qty,
                    'price_unit': line.price_unit,
                    'date_start': fields.Date.context_today(self),
                    'recurring_interval': 1,
                    'recurring_rule_type': template.hestiacp_billing_period,
                    'recurring_invoicing_type': 'pre-paid',
                })],
            })
            checkout_tx = self.get_portal_last_transaction()
            account = self.env['hestiacp.account'].create({
                'partner_id': self.partner_id.id,
                'server_id': template.hestiacp_server_id.id,
                'product_id': template.id,
                'sale_order_id': self.id,
                'contract_id': contract.id,
                # Only set if the customer tokenized their card at checkout
                # (declined, or a non-tokenizing payment method like a bank
                # transfer, just means renewals wait for manual payment -
                # see payment_token_id's help text).
                'payment_token_id': checkout_tx.token_id.id if checkout_tx else False,
                # Copied from the order, where the checkout's own agreement
                # page (controllers/agreement.py) recorded it before
                # payment was ever reachable - see
                # _hestiacp_requires_aup_acceptance. A backend-confirmed
                # order (e.g. a salesperson confirming a phone quote)
                # never goes through that page, so these can be empty;
                # action_provision logs that on the account's chatter
                # rather than blocking provisioning outright.
                'aup_agreement_id': self.hestiacp_aup_agreement_id.id,
                'aup_accepted_on': self.hestiacp_aup_accepted_on,
                'aup_accepted_ip': self.hestiacp_aup_accepted_ip,
            })
            account.action_provision()
