# -*- coding: utf-8 -*-
from odoo import api, fields, models


class GigTimelineLine(models.Model):
    """One moment in the gig's timeline: 18:00 Grand entrance, 18:15 First
    dance... Times are hours of the day; on a gig that runs past midnight,
    times up to its end count as after midnight."""
    _name = 'gig.timeline.line'
    _description = 'Gig Timeline'
    _order = 'order_id, sort_hour, sequence, id'

    order_id = fields.Many2one('sale.order', required=True, ondelete='cascade', index=True)
    hour = fields.Float(string="Time", required=True)
    moment = fields.Char(required=True, help="e.g. Grand entrance, First dance, Toasts, Last song.")
    note = fields.Char(help="Who, which song, cues...")
    added_by_client = fields.Boolean(readonly=True)
    sort_hour = fields.Float(compute='_compute_sort_hour', store=True)
    sequence = fields.Integer(default=10)

    @api.depends('hour', 'order_id.gig_start_hour', 'order_id.gig_end_hour')
    def _compute_sort_hour(self):
        for line in self:
            order = line.order_id
            past_midnight = order.gig_end_hour < order.gig_start_hour
            line.sort_hour = line.hour + 24 if past_midnight and line.hour <= order.gig_end_hour else line.hour

    def _hhmm(self):
        return self.order_id._gig_hhmm(self.hour) or '00:00'
