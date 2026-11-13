# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    stripe_tax_code = fields.Char(
        string="Stripe Tax Code",
        help="What Stripe Tax should treat this product as, e.g. "
             "txcd_10103001 (SaaS, business use) or txcd_10701100 (website "
             "hosting). Leave empty for anything that isn't taxed this way "
             "(domains, setup fees, phone service). Codes: "
             "https://docs.stripe.com/tax/tax-codes")
