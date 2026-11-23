# -*- coding: utf-8 -*-
from odoo import api, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.depends('order_id.gig_start', 'order_id.gig_end', 'product_id.gig_bill_hours')
    def _compute_product_uom_qty(self):
        super()._compute_product_uom_qty()
        self._gig_set_hours()

    def _gig_set_hours(self):
        """Hourly gig products: the quantity is the gig's hours."""
        for line in self:
            if line.display_type or not line.product_id.gig_bill_hours:
                continue
            if line.order_id.state not in ('draft', 'sent'):
                continue  # booked: what was agreed stays
            hours = line.order_id._gig_billable_hours()
            if hours and line.product_uom_qty != hours:
                line.product_uom_qty = hours

    @api.model_create_multi
    def create(self, vals_list):
        # A new line gets the default quantity without computing it.
        lines = super().create(vals_list)
        lines._gig_set_hours()
        return lines


class SaleOrderTemplateLine(models.Model):
    _inherit = 'sale.order.template.line'

    def _prepare_order_line_values(self):
        """Hourly gig products take the gig's hours, not the template's quantity."""
        vals = super()._prepare_order_line_values()
        if self.product_id.gig_bill_hours:
            vals.pop('product_uom_qty', None)
        return vals
