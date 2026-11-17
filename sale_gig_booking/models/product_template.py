# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    gig_bill_hours = fields.Boolean(
        string="Bill the Gig's Hours",
        help="On a gig's quote, the quantity follows the gig's length (start to end), "
             "never below the company's minimum hours.")
    gig_booked_todo = fields.Text(
        string="To-do When Booked",
        help="When a gig with this product is booked, this becomes a to-do for the salesperson. "
             "First line: the to-do's title; the rest: its notes.")
