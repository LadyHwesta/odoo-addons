# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class SignalWirePiperController(http.Controller):

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
