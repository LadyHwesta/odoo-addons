# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_domain_registration = fields.Boolean(
        help="Marks this as the generic \"buy a domain\" product - price "
             "isn't fixed per product like a normal SKU, since it varies by "
             "TLD and by domain (premium names have their own price); the "
             "website search page sets each order line's own price_unit "
             "directly from namecheap.tld.price / a domain's premium price "
             "at add-to-cart time, this product just carries the line. "
             "Leave unpublished on the website - customers reach it "
             "through the domain search page, not the normal shop.")
    namecheap_server_id = fields.Many2one(
        'namecheap.server', string="Namecheap Account",
        help="Which Namecheap account this product registers domains "
             "through.")
