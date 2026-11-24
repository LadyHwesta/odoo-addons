# -*- coding: utf-8 -*-
from odoo import models


class ResCompany(models.Model):
    _inherit = 'res.company'

    def _donation_cover_fee_rates(self):
        """Add Meskis' fee when this company takes its payments through Meskis."""
        percent, fixed = super()._donation_cover_fee_rates()
        company = self.sudo()
        bridged = self.env['payment.provider'].sudo().search_count([
            ('code', '=', 'stripe'), ('stripe_connect_bridged', '=', True),
            ('state', '=', 'enabled'), ('company_id', '=', company.id),
        ], limit=1)
        if bridged:
            percent += company.stripe_connect_fee_percent or 0.0
        return percent, fixed
