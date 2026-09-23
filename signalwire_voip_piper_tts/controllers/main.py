# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.http import request

from ..models.piper_client import PiperError

_logger = logging.getLogger(__name__)


class SignalWirePiperController(http.Controller):

    @http.route(
        '/signalwire/piper/preview', type='http', auth='user',
        methods=['POST'])
    def piper_preview(self, text=None, voice=None, speaker_id=None, **kwargs):
        """Backend-only "Preview" button support - synthesizes `text`
        on demand and returns the raw WAV directly, so a form's own
        Voice/Speaker choice can be heard without saving, without
        placing a real call, and without touching signalwire.piper.
        audio.cache at all (a one-off sample typed just to compare
        voices has no business becoming a permanent cached greeting).
        `auth='user'` (any logged-in internal user, matching the same
        access level self-service voicemail preferences already have)
        rather than 'public' - unlike /piper_audio above, this route
        actively calls out to Piper on every request, so it shouldn't
        be reachable by a logged-out caller.
        """
        text = (text or '').strip()
        if not text or not voice:
            return request.make_response(
                json.dumps({'error': "Text and voice are both required."}),
                headers=[('Content-Type', 'application/json')], status=400)
        server = request.env['signalwire.server'].sudo().search([], limit=1)
        if not server or not server.piper_url:
            return request.make_response(
                json.dumps({'error': "Piper isn't configured (signalwire.server.piper_url is empty)."}),
                headers=[('Content-Type', 'application/json')], status=400)
        try:
            speaker_id = int(speaker_id) if speaker_id else None
            wav_bytes = server._get_piper_client().synthesize(text, voice, speaker_id)
        except PiperError as exc:
            _logger.info("Piper: preview synthesis failed: %s", exc)
            return request.make_response(
                json.dumps({'error': str(exc)}),
                headers=[('Content-Type', 'application/json')], status=400)
        return request.make_response(
            wav_bytes, headers=[('Content-Type', 'audio/wav')])

    @http.route(
        '/signalwire/voice/piper_audio/<int:attachment_id>',
        type='http', auth='public', methods=['GET'])
    def piper_audio(self, attachment_id, **kwargs):
        """Serves a Piper-synthesized greeting to SignalWire's media
        server, which fetches <Play> URLs directly and unauthenticated
        - same shape as signalwire_voip_click2call's own
        /signalwire/voice/greeting/<id> route. Scoped to attachments
        actually referenced by a signalwire.piper.audio.cache row, not
        an open-ended attachment-id fetch - same accepted-risk
        reasoning as that route: low-sensitivity content (a spoken
        greeting, not private data), publicly reachable by necessity,
        narrowly scoped rather than wide open.
        """
        cache_row = request.env['signalwire.piper.audio.cache'].sudo().search(
            [('audio_attachment_id', '=', attachment_id)], limit=1)
        if not cache_row:
            return request.not_found()
        stream = request.env['ir.binary']._get_stream_from(
            cache_row.audio_attachment_id, 'raw')
        return stream.get_response(as_attachment=False, max_age=None)
