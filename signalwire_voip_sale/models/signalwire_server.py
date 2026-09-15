# -*- coding: utf-8 -*-
from odoo import fields, models


class SignalWireServer(models.Model):
    _inherit = 'signalwire.server'

    markup_percentage = fields.Float(
        string="Usage Markup %", default=20.0, required=True,
        help="Applied over SignalWire's own real per-call/per-message "
             "cost when billing a customer's metered usage line - a "
             "single global percentage, same convention as "
             "namecheap.server's own markup_percentage.")
