# -*- coding: utf-8 -*-
from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    signalwire_phone_number = fields.Char(
        help="The specific number this line buys, e.g. \"+12084449665\" "
             "- set by the VoIP search page's add-to-cart action, not "
             "editable from a normal product line.")
