# -*- coding: utf-8 -*-
import logging
import re
from datetime import timedelta

from odoo import fields, http
from odoo.http import request
from werkzeug.exceptions import NotFound

from odoo.addons.signalwire_voip.models.signalwire_api import SignalWireAPIError

_logger = logging.getLogger(__name__)
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
# Watching stays open this long after the meeting's planned end.
GRACE = timedelta(hours=2)


class PublicMeetingController(http.Controller):

    def _event(self, field, token):
        event = request.env['calendar.event'].sudo().search(
            [(field, '=', token), ('public_meeting', '=', True)], limit=1) if token else None
        if not event:
            raise NotFound()
        return event

    def _ended(self, event):
        return event.stop and fields.Datetime.now() > event.stop + GRACE

    def _room_page(self, event, token, role):
        return request.render('calendar_public_meeting.room_page', {
            'event': event, 'room_token': token, 'role': role,
            'documents': event._public_documents()})

    def _error_page(self, event, message):
        return request.render('calendar_public_meeting.message_page', {
            'event': event, 'message': message})

    @http.route('/meeting/watch/<string:token>', type='http', auth='public', website=True,
                sitemap=False, methods=['GET', 'POST'])
    def watch(self, token, **post):
        """The public's page: name and email, then a view-only seat."""
        event = self._event('public_watch_token', token)
        if self._ended(event):
            return self._error_page(event, request.env._("This meeting has ended."))
        values = {'event': event, 'documents': event._public_documents(), 'error': None,
                  'name': (post.get('name') or '').strip(),
                  'email': (post.get('email') or '').strip()}
        if request.httprequest.method == 'POST':
            if not values['name'] or not EMAIL_RE.match(values['email']):
                values['error'] = request.env._("Please enter your name and a valid email.")
            else:
                request.env['calendar.public.viewer'].sudo().create({
                    'event_id': event.id, 'name': values['name'][:100],
                    'email': values['email'][:254]})
                try:
                    room_token = event._public_room_token(values['name'], viewer=True)
                except SignalWireAPIError:
                    _logger.exception("Public meeting %s: no viewer token", event.id)
                    return self._error_page(event, request.env._(
                        "The meeting can't be joined right now. Please try again in a few minutes."))
                return self._room_page(event, room_token, 'viewer')
        return request.render('calendar_public_meeting.watch_page', values)

    @http.route('/meeting/join/<string:token>', type='http', auth='public', website=True,
                sitemap=False, methods=['GET', 'POST'])
    def join(self, token, **post):
        """The speakers' page, from the link in their invitation."""
        event = self._event('access_token', token)
        if self._ended(event):
            return self._error_page(event, request.env._("This meeting has ended."))
        user = request.env.user
        name = (post.get('name') or '').strip() or ('' if user._is_public() else user.name)
        if not name:
            return request.render('calendar_public_meeting.join_page', {'event': event})
        try:
            room_token = event._public_room_token(name, viewer=False)
        except SignalWireAPIError:
            _logger.exception("Public meeting %s: no speaker token", event.id)
            return self._error_page(event, request.env._(
                "The meeting can't be joined right now. Please try again in a few minutes."))
        return self._room_page(event, room_token, 'speaker')
