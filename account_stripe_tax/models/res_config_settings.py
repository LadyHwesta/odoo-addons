# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    stripe_tax_provider_id = fields.Many2one(
        related='company_id.stripe_tax_provider_id', readonly=False)
    stripe_tax_account_id = fields.Many2one(
        related='company_id.stripe_tax_account_id', readonly=False)
    stripe_tax_record_all = fields.Boolean(
        related='company_id.stripe_tax_record_all', readonly=False)
