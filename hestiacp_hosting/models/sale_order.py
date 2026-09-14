# -*- coding: utf-8 -*-
from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

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
                    'recurring_rule_type': 'monthly',
                    'recurring_invoicing_type': 'pre-paid',
                })],
            })
            account = self.env['hestiacp.account'].create({
                'partner_id': self.partner_id.id,
                'server_id': template.hestiacp_server_id.id,
                'product_id': template.id,
                'sale_order_id': self.id,
                'contract_id': contract.id,
            })
            account.action_provision()
