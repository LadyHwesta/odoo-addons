# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    stripe_tax_exempt = fields.Boolean(
        string="Exempt from Sales Tax",
        help="Stripe Tax charges this customer no sales tax. Keep their "
             "exemption certificate on file.")
