# -*- coding: utf-8 -*-
import json
import logging
import re
from datetime import timedelta

from odoo import Command, fields, http
from odoo.http import request
from werkzeug.exceptions import BadRequest, Forbidden, NotFound

from odoo.addons.signalwire_voip.models.signalwire_api import SignalWireAPIError

from ..models.calendar_event import CHAT_MAX, QUESTION_MAX

_logger = logging.getLogger(__name__)
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
# Watching stays open this long after the meeting's planned end.
GRACE = timedelta(hours=2)
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
# Shortest gap between two messages from one seat: speakers chat, the public
# asks questions (so 300 viewers can't flood the speakers' list).
SPEAKER_WAIT = timedelta(seconds=1)
QUESTION_WAIT = timedelta(seconds=15)


class PublicMeetingController(http.Controller):

    def _event(self, field, token):
        event = request.env['calendar.event'].sudo().search(
            [(field, '=', token), ('public_meeting', '=', True)], limit=1) if token else None
        if not event:
            raise NotFound()
        return event

    def _ended(self, event):
        return event.stop and fields.Datetime.now() > event.stop + GRACE

    def _room_page(self, event, token, role, name, viewer=None):
        seat = event._public_seat(name, role, viewer=viewer)
        return request.render('calendar_public_meeting.room_page', {
            'event': event, 'room_token': token, 'role': role, 'seat_key': seat.key,
            'name': name, 'documents': event._public_documents(),
            'documents_version': event._public_documents_version(),
            'max_upload_mb': MAX_UPLOAD_BYTES // (1024 * 1024),
            'question_max': QUESTION_MAX, 'chat_max': CHAT_MAX})

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
                viewer = request.env['calendar.public.viewer'].sudo().create({
                    'event_id': event.id, 'name': values['name'][:100],
                    'email': values['email'][:254]})
                try:
                    room_token = event._public_room_token(values['name'], viewer=True)
                except SignalWireAPIError:
                    _logger.exception("Public meeting %s: no viewer token", event.id)
                    return self._error_page(event, request.env._(
                        "The meeting can't be joined right now. Please try again in a few minutes."))
                return self._room_page(event, room_token, 'viewer', values['name'], viewer=viewer)
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
        return self._room_page(event, room_token, 'speaker', name)

    # -- In the room: chat, questions, documents --------------------------------
    # The page calls these with its seat key, a secret only that page has, so
    # no CSRF token is needed: a forged request can't know the key.

    def _seat(self, key, role=None):
        seat = request.env['calendar.public.seat'].sudo().search(
            [('key', '=', key)], limit=1) if key and len(key) >= 32 else None
        if not seat or not seat.event_id.public_meeting or self._ended(seat.event_id) \
                or (role and seat.role != role):
            raise Forbidden()
        return seat

    def _json_body(self):
        try:
            return json.loads(request.httprequest.get_data(as_text=True) or '{}')
        except ValueError:
            raise BadRequest()

    def _too_soon(self, seat):
        wait = SPEAKER_WAIT if seat.role == 'speaker' else QUESTION_WAIT
        now = fields.Datetime.now()
        if seat.last_sent and now < seat.last_sent + wait:
            return True
        seat.last_sent = now
        return False

    @http.route('/meeting/room/<string:key>/poll', type='http', auth='public', methods=['POST'],
                csrf=False, sitemap=False)
    def room_poll(self, key, **_kw):
        """Speakers' pages ask every few seconds: new chat and questions, and
        whether the shared documents changed."""
        seat = self._seat(key, role='speaker')
        data = self._json_body()
        after = data.get('after') if isinstance(data.get('after'), int) else 0
        event = seat.event_id
        messages = request.env['calendar.public.message'].sudo().search(
            [('event_id', '=', event.id), ('id', '>', after)], limit=200)
        changed = request.env['calendar.public.message'].sudo().search(
            [('event_id', '=', event.id), ('kind', '=', 'question'), ('id', '<=', after)])
        version = event._public_documents_version()
        result = {'messages': messages._to_json(),
                  'answered': changed.filtered('answered').ids,
                  'documents_version': version}
        if data.get('documents_version') != version:
            result['documents'] = event._public_documents()
        return request.make_json_response(result)

    @http.route('/meeting/room/<string:key>/send', type='http', auth='public', methods=['POST'],
                csrf=False, sitemap=False)
    def room_send(self, key, **_kw):
        """A speaker's chat message, or a viewer's question."""
        seat = self._seat(key)
        body = self._json_body().get('body')
        body = body.strip() if isinstance(body, str) else ''
        if not body:
            raise BadRequest()
        # Speakers chat; viewers can only ask.
        kind = 'chat' if seat.role == 'speaker' else 'question'
        if self._too_soon(seat):
            return request.make_json_response({'error': 'wait'}, status=429)
        message = request.env['calendar.public.message'].sudo().create({
            'event_id': seat.event_id.id, 'seat_id': seat.id, 'author_name': seat.name,
            'kind': kind, 'body': body[:CHAT_MAX if kind == 'chat' else QUESTION_MAX]})
        return request.make_json_response({'message': message._to_json()[0]})

    @http.route('/meeting/room/<string:key>/answered', type='http', auth='public',
                methods=['POST'], csrf=False, sitemap=False)
    def room_answered(self, key, **_kw):
        seat = self._seat(key, role='speaker')
        data = self._json_body()
        question = request.env['calendar.public.message'].sudo().search([
            ('id', '=', data.get('id') if isinstance(data.get('id'), int) else 0),
            ('event_id', '=', seat.event_id.id), ('kind', '=', 'question')])
        if not question:
            raise NotFound()
        question.answered = bool(data.get('answered', True))
        return request.make_json_response({'ok': True})

    @http.route('/meeting/room/<string:key>/documents', type='http', auth='public',
                methods=['GET'], sitemap=False)
    def room_documents(self, key, **_kw):
        """The shared documents, for viewers' pages when a speaker says they changed."""
        seat = self._seat(key)
        return request.make_json_response({
            'documents': seat.event_id._public_documents(),
            'documents_version': seat.event_id._public_documents_version()})

    @http.route('/meeting/room/<string:key>/upload', type='http', auth='public',
                methods=['POST'], csrf=False, sitemap=False)
    def room_upload(self, key, **post):
        """A speaker adds a document: it joins the meeting's Documents, shared."""
        seat = self._seat(key, role='speaker')
        upload = post.get('file')
        if not upload or not getattr(upload, 'filename', None):
            raise BadRequest()
        content = upload.read(MAX_UPLOAD_BYTES + 1)
        if len(content) > MAX_UPLOAD_BYTES:
            return request.make_json_response({'error': 'too_large'}, status=413)
        event = seat.event_id.sudo()
        attachment = request.env['ir.attachment'].sudo().create({
            'name': upload.filename[:200], 'raw': content,
            'res_model': 'calendar.event', 'res_id': event.id})
        event.document_ids = [Command.link(attachment.id)]
        event.message_post(body=request.env._(
            "%(name)s added %(file)s during the public meeting.",
            name=seat.name, file=attachment.name))
        return request.make_json_response({
            'documents': event._public_documents(),
            'documents_version': event._public_documents_version()})
