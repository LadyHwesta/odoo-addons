# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

from odoo.addons.signalwire_voip.webhook_security import signalwire_signed

CXML_ACK = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'


class SignalWireSmsController(http.Controller):

    @http.route(
        '/signalwire/sms/inbound', type='http', auth='public',
        methods=['POST'], csrf=False)
    @signalwire_signed
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
            message._handle_inbound_keywords()

        return request.make_response(CXML_ACK, headers=[('Content-Type', 'text/xml')])

    @http.route(
        '/signalwire/sms/status', type='http', auth='public',
        methods=['POST'], csrf=False)
    @signalwire_signed
    def sms_status(self, **kwargs):
        """SignalWire's delivery reports for texts Odoo sent (the
        StatusCallback given in send_sms): queued, sent, delivered,
        undelivered, failed. Only updates a message SignalWire already
        gave Odoo the ID of, so a stray or made-up post changes nothing."""
        form = request.httprequest.form
        sid, status = form.get('MessageSid', ''), form.get('MessageStatus', '')
        if sid and status:
            message = request.env['signalwire.sms'].sudo().search(
                [('sid', '=', sid), ('direction', '=', 'outbound')], limit=1)
            if message:
                error = form.get('ErrorCode')
                message.state = f'{status} ({error})' if error else status
        return request.make_response('', status=204)
