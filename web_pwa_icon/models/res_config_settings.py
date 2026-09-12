# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pwa_icon = fields.Image(
        related='company_id.pwa_icon', readonly=False,
        string='Progressive Web App Icon',
    )
