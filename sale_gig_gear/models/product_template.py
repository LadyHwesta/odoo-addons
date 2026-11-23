# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    gig_gear_default_ids = fields.One2many(
        'gig.gear.default', 'product_tmpl_id', string="Gig Gear",
        help="Gear a gig with this package or add-on needs; added to the gig's checklist.")
