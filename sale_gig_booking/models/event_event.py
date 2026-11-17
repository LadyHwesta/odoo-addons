# -*- coding: utf-8 -*-
from odoo import fields, models


class EventEvent(models.Model):
    _inherit = 'event.event'

    gig_order_ids = fields.One2many('sale.order', 'gig_event_id', string="Gig Bookings")
