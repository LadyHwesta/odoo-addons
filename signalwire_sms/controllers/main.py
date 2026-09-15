# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

CXML_ACK = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'


class SignalWireSmsController(http.Controller):

    @http.route(
        '/signalwire/sms/inbound', type='http', auth='public',
        methods=['POST'], csrf=False)
    def inbound_sms(self, **kwargs):
        """SignalWire POSTs standard Twilio-compatible form fields
        here (To, From, Body, MessageSid, ...) on every inbound SMS to
        any number whose SMS URL points here. An empty cXML response
        means "received, no auto-reply" - the standard way to just
        accept a message without SignalWire expecting one back.
        """
        form = request.httprequest.form
        to_number = form.get('To', '')
        number = request.env['signalwire.phone_number'].sudo().search(
            [('name', '=', to_number)], limit=1)

        if number:
            message = request.env['signalwire.sms'].sudo().create({
                'phone_number_id': number.id,
                'direction': 'inbound',
                'from_number': form.get('From', ''),
                'to_number': to_number,
                'body': form.get('Body', ''),
                'sid': form.get('MessageSid', ''),
                'state': 'received',
            })
            message._log_to_partner_chatter()
            message._forward_to_customer_webhook()

        return request.make_response(CXML_ACK, headers=[('Content-Type', 'text/xml')])
