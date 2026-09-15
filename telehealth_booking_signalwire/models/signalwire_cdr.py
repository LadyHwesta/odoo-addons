# -*- coding: utf-8 -*-
from odoo import fields, models


class SignalWireCdr(models.Model):
    _inherit = 'signalwire.cdr'

    record_type = fields.Selection(
        selection_add=[('video', 'Video')], ondelete={'video': 'cascade'})
