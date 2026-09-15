# -*- coding: utf-8 -*-
from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    namecheap_domain_name = fields.Char(
        help="The specific domain this line registers, e.g. "
             "\"example.com\" - set by the domain search page's add-to-cart "
             "action, not editable from a normal product line.")
    namecheap_years = fields.Integer(
        default=1, help="Registration length in years.")
