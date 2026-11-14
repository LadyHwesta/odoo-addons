# -*- coding: utf-8 -*-
"""Meetings the public can watch.

A public meeting runs in a video room on the phone service's video API,
everyone in it billed per minute. Speakers (the attendees) join from the
meeting's own link; the public from a separate watch link, with a token that
can't unmute, turn on a camera or share a screen. The provider's view-only
"audience" role is being retired, so viewers are ordinary participants
without those permissions.
"""
import uuid

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

ROOM_LIMIT = 300  # the most people a video room holds
JOIN_ROUTE = 'meeting/join'
WATCH_ROUTE = 'meeting/watch'
# What a viewer may do: listen, and set their own volume.
VIEWER_PERMISSIONS = ['room.self.deaf', 'room.self.undeaf', 'room.self.set_output_volume']


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    public_meeting = fields.Boolean(
        string="Public Meeting", copy=False,
        help="Anyone with the Watch Link can watch and listen after giving their name "
             "and email. Attendees speak from their invitation link. A paid video "
             "service: every speaker and viewer is billed per minute.")
    public_max_viewers = fields.Integer(
        string="Viewer Limit", default=100,
        help="The most people who can watch at once, up to 299.")
    public_watch_token = fields.Char(copy=False, readonly=True, index=True)
    public_watch_url = fields.Char(string="Watch Link", compute='_compute_public_watch_url')
    public_room_name = fields.Char(copy=False, readonly=True)
    public_viewer_ids = fields.One2many('calendar.public.viewer', 'event_id', string="Viewers")
    public_viewer_count = fields.Integer(compute='_compute_public_viewer_count')

    @api.constrains('public_max_viewers', 'public_meeting')
    def _check_public_max_viewers(self):
        for event in self.filtered('public_meeting'):
            if not 1 <= event.public_max_viewers < ROOM_LIMIT:
                raise ValidationError(self.env._(
                    "The viewer limit must be between 1 and %(max)s.", max=ROOM_LIMIT - 1))

    @api.depends('public_meeting', 'public_watch_token')
    def _compute_public_watch_url(self):
        for event in self:
            event.public_watch_url = event.public_meeting and event.public_watch_token and \
                f"{event.get_base_url()}/{WATCH_ROUTE}/{event.public_watch_token}"

    @api.depends('public_viewer_ids')
    def _compute_public_viewer_count(self):
        for event in self:
            event.public_viewer_count = len(event.public_viewer_ids)

    @api.model_create_multi
    def create(self, vals_list):
        events = super().create(vals_list)
        events.filtered('public_meeting')._setup_public_meeting()
        return events

    def write(self, vals):
        result = super().write(vals)
        if 'public_meeting' in vals:
            self.filtered('public_meeting')._setup_public_meeting()
            self.filtered(lambda e: not e.public_meeting)._drop_public_meeting()
        return result

    def _speaker_join_url(self):
        self.ensure_one()
        return f"{self.get_base_url()}/{JOIN_ROUTE}/{self.access_token}"

    def _setup_public_meeting(self):
        """Gives the meeting its watch link, and points its video link (the one
        in invitations) at the speakers' page."""
        for event in self:
            if not event._video_server():
                raise UserError(self.env._(
                    "Public meetings need the phone service connected (Phone > "
                    "Configuration > Phone Accounts)."))
            values = {}
            if not event.public_watch_token:
                values['public_watch_token'] = uuid.uuid4().hex
            if not event.access_token:
                values['access_token'] = uuid.uuid4().hex
            if values:
                super(CalendarEvent, event).write(values)
            if event.videocall_location != event._speaker_join_url():
                super(CalendarEvent, event).write({'videocall_location': event._speaker_join_url()})

    def _set_discuss_videocall_location(self):
        # "+ Odoo meeting" on a public meeting keeps the speakers' link.
        if self.public_meeting and self.access_token:
            self.videocall_location = self._speaker_join_url()
            return
        return super()._set_discuss_videocall_location()

    def _drop_public_meeting(self):
        for event in self:
            if event.access_token and event.videocall_location == event._speaker_join_url():
                super(CalendarEvent, event).write({'videocall_location': False})

    # -- The video room ---------------------------------------------------------

    def _video_server(self):
        return self.env['signalwire.server'].sudo().search([], limit=1)

    def _public_room(self):
        """The meeting's video room, made the first time someone joins."""
        self.ensure_one()
        if not self.public_room_name:
            name = f"meeting-{self.id}-{uuid.uuid4().hex[:8]}"
            speakers = len(self.partner_ids) + 5
            self._video_server()._get_client().video_post(
                'rooms', name=name, display_name=(self.name or '')[:200],
                max_members=min(self.public_max_viewers + speakers, ROOM_LIMIT),
                quality='720p', layout='grid-responsive')
            self.sudo().public_room_name = name
        return self.public_room_name

    def _public_room_token(self, user_name, viewer):
        """A fresh room token for one person: a speaker, or a view-only viewer."""
        self.ensure_one()
        body = {'room_name': self._public_room(), 'user_name': (user_name or '')[:100]}
        if viewer:
            body.update({'permissions': VIEWER_PERMISSIONS,
                         'join_audio_muted': True, 'join_video_muted': True})
        return self._video_server()._get_client().video_post('room_tokens', **body)['token']

    def _public_documents(self):
        """Documents shown on the watch and join pages: the ones that aren't
        private, each with its own download link."""
        self.ensure_one()
        documents = self.sudo()._shared_documents()
        base = self.get_base_url()
        return [{'name': d.name,
                 'url': f"{base}/web/content/{d.id}?access_token="
                        f"{d.sudo().generate_access_token()[0]}&download=true"}
                for d in documents]


class CalendarPublicViewer(models.Model):
    _name = 'calendar.public.viewer'
    _description = 'Public Meeting Viewer'
    _order = 'create_date desc'

    event_id = fields.Many2one('calendar.event', required=True, ondelete='cascade', index=True)
    name = fields.Char(required=True)
    email = fields.Char(required=True)
    create_date = fields.Datetime(string="Signed In", readonly=True)
