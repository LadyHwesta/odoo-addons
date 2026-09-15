# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_voip_number = fields.Boolean(
        help="Marks this as the generic \"buy a VoIP number\" product - "
             "the website search page always uses the first such "
             "product found with a SignalWire account set. This "
             "product's own list_price is the flat monthly number-"
             "rental fee; actual usage (calls/SMS) is billed "
             "separately, on a second contract line whose price is "
             "computed fresh each period from real usage - see "
             "contract.line's own override in this module.")
    signalwire_server_id = fields.Many2one(
        'signalwire.server', string="SignalWire Account",
        help="Which SignalWire project this product provisions "
             "numbers through.")
