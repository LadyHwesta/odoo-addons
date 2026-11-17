# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    gig_buffer_hours = fields.Float(related='company_id.gig_buffer_hours', readonly=False)
    gig_balance_days = fields.Integer(related='company_id.gig_balance_days', readonly=False)
    gig_min_hours = fields.Float(related='company_id.gig_min_hours', readonly=False)
    gig_tz = fields.Selection(related='company_id.gig_tz', readonly=False)
