# -*- coding: utf-8 -*-
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

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
    # Getting the track before the gig (must-play songs and guest requests).
    acquire_state = fields.Selection(
        [('to_get', "To get"), ('got', "Got it"), ('unavailable', "Can't get")],
        string="Track", default='to_get', required=True)
    acquire_note = fields.Char(
        string="Why Not", help="Why you can't get it. The client sees this on their must-play list.")
    gig_date = fields.Date(related='order_id.gig_date', string="Gig Date")
    requester_key = fields.Char(copy=False)
    sequence = fields.Integer(default=10)

    @api.depends('song', 'kind', 'order_id.song_request_ids.song', 'order_id.song_request_ids.kind')
    def _compute_on_do_not_play(self):
        for line in self:
            banned = {song_key(r.song) for r in line.order_id.song_request_ids if r.kind == 'do_not_play'}
            line.on_do_not_play = line.kind == 'request' and song_key(line.song) in banned

    def action_got_it(self):
        self.write({'acquire_state': 'got', 'acquire_note': False})

    def action_cant_get(self):
        """Ask why, then mark it: the note is shown to the client."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _("Can't get this song"),
            'res_model': self._name, 'res_id': self.id, 'view_mode': 'form', 'target': 'new',
            'views': [(self.env.ref('sale_gig_song_requests.gig_song_request_view_form_cant_get').id, 'form')],
        }

    def action_confirm_cant_get(self):
        for line in self:
            if not (line.acquire_note or '').strip():
                raise UserError(_("Say why you can't get it: the client sees the note."))
        self.acquire_state = 'unavailable'
        return {'type': 'ir.actions.act_window_close'}

    def action_reset_acquire(self):
        self.write({'acquire_state': 'to_get', 'acquire_note': False})

    def action_played(self):
        self.state = 'played'

    def action_skipped(self):
        self.state = 'skipped'

    def action_reset(self):
        self.state = 'new'
