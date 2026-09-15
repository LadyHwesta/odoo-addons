# -*- coding: utf-8 -*-
from odoo import _, fields, models


class HestiaCPAccount(models.Model):
    _inherit = 'hestiacp.account'

    def _subscription_summary(self):
        self.ensure_one()
        line = self.env['contract.line']
        if self.contract_id:
            today = fields.Date.context_today(self)
            line = self.contract_id.contract_line_ids.filtered(
                lambda l: not l.date_end or l.date_end >= today)[:1]
        return {
            'name': _("Hosting: %(package)s", package=self.product_id.name),
            'state': self.state,
            'next_invoice_date': line.recurring_next_date if line else False,
            'monthly_amount': line.price_unit if line else 0.0,
            'can_upgrade': self.state == 'active',
            'can_cancel': self.state in ('active', 'suspended'),
            'has_payment_method': bool(self.payment_token_id),
            'portal_view_url': '/my/hosting',
        }
