# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

CXML_HEADER = '<?xml version="1.0" encoding="UTF-8"?>'


class SignalWireVoiceController(http.Controller):

    @http.route(
        '/signalwire/voice/inbound', type='http', auth='public',
        methods=['POST'], csrf=False)
    def inbound_call(self, **kwargs):
        """SignalWire POSTs standard Twilio-compatible form fields
        here (To, From, CallSid, ...) on every inbound call to any
        number whose Voice URL points here, and expects cXML back
        telling it what to do. Looked up by the "To" number rather
        than a per-number URL, so this one webhook serves every
        purchased number - simpler to configure than a unique callback
        URL per number.
        """
        to_number = request.httprequest.form.get('To', '')
        number = request.env['signalwire.phone_number'].sudo().search(
            [('name', '=', to_number)], limit=1)
        user = number.assigned_user_id if number else request.env['res.users']

        if not user or not user.voip_username:
            # No one to ring - politely decline rather than let the
            # caller hang in silence.
            cxml = f'{CXML_HEADER}<Response><Reject/></Response>'
        else:
            sip_domain = number.subproject_id.server_id._get_sip_domain()
            cxml = (
                f'{CXML_HEADER}<Response><Dial>'
                f'<Sip>sip:{user.voip_username}@{sip_domain}</Sip>'
                f'</Dial></Response>'
            )
        return request.make_response(cxml, headers=[('Content-Type', 'text/xml')])
