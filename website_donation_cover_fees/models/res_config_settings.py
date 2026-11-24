# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    currency_id = fields.Many2one(related='company_id.currency_id')
    donation_cover_fees = fields.Boolean(
        related='company_id.donation_cover_fees', readonly=False)
    donation_fee_percent = fields.Float(
        related='company_id.donation_fee_percent', readonly=False)
    donation_fee_fixed = fields.Monetary(
        related='company_id.donation_fee_fixed', readonly=False,
        currency_field='currency_id')
