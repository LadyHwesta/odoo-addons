# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    stripe_connect_bridge_url = fields.Char(
        related='company_id.stripe_connect_bridge_url', readonly=False)
    stripe_connect_bridge_token = fields.Char(
        related='company_id.stripe_connect_bridge_token', readonly=False)
    stripe_connect_account_id = fields.Char(
        related='company_id.stripe_connect_account_id', readonly=False)
