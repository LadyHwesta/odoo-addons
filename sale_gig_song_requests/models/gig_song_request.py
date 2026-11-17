# -*- coding: utf-8 -*-
import re

from odoo import api, fields, models

KINDS = [('request', "Guest request"), ('must_play', "Must play"), ('do_not_play', "Do not play")]


def song_key(song):
    """Titles compared loosely: case, punctuation and spacing don't matter."""
    return re.sub(r'[^\w]+', ' ', (song or '').lower()).strip()


class GigSongRequest(models.Model):
    _name = 'gig.song.request'
    _description = 'Song Request'
    _order = 'sequence, create_date desc, id desc'

    order_id = fields.Many2one('sale.order', string="Gig", required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='order_id.company_id', store=True)
    kind = fields.Selection(KINDS, required=True, default='request')
    song = fields.Char(required=True)
    artist = fields.Char()
    requested_by = fields.Char(string="From")
    note = fields.Char(help="For must-play songs: the moment, e.g. First dance, Grand entrance.")
    state = fields.Selection([('new', "New"), ('played', "Played"), ('skipped', "Skipped")],
                             default='new', required=True)
    on_do_not_play = fields.Boolean(compute='_compute_on_do_not_play', string="On Do-not-play")
    requester_key = fields.Char(copy=False)
    sequence = fields.Integer(default=10)

    @api.depends('song', 'kind', 'order_id.song_request_ids.song', 'order_id.song_request_ids.kind')
    def _compute_on_do_not_play(self):
        for line in self:
            banned = {song_key(r.song) for r in line.order_id.song_request_ids if r.kind == 'do_not_play'}
            line.on_do_not_play = line.kind == 'request' and song_key(line.song) in banned

    def action_played(self):
        self.state = 'played'

    def action_skipped(self):
        self.state = 'skipped'

    def action_reset(self):
        self.state = 'new'
