# -*- coding: utf-8 -*-
"""Outside calls placed from a softphone, routed through Odoo.

LIVE TEST (2026-11-17): the provider doesn't document whether a SIP
endpoint with call_handler "laml_webhooks" asks its call_request_url when
it DIALS OUT. This route answers that: it logs every field the provider
sends, then places the call exactly as the endpoint would on its own
(the person's Calls Out As number, same E911 rule), so the test call
works normally. Once confirmed, the caller ID is chosen per company here.
"""
import logging
import re
from xml.sax import saxutils

from odoo import http
from odoo.http import request

from odoo.addons.signalwire_voip.webhook_security import signalwire_signed

_logger = logging.getLogger(__name__)

SIP_USER_RE = re.compile(r'^sips?:([^@;>]+)@', re.I)


def sip_user(address):
    """'sip:tiesa.meskis2@x.sip.signalwire.com' -> 'tiesa.meskis2'."""
    match = SIP_USER_RE.match((address or '').strip().strip('<>'))
    return match.group(1) if match else ''


def dialed_number(to):
    """The phone number dialed: E.164 for 10/11-digit North American
    numbers, the digits otherwise ('911', short codes). '' when `to` is
    not a phone number (another SIP user)."""
    user = sip_user(to) or (to or '').strip()
    if user.startswith('+') and user[1:].isdigit():
        return user
    digits = re.sub(r'\D', '', user)
    if not digits or digits != re.sub(r'[\s().\-]', '', user).lstrip('+'):
        return ''
    if len(digits) == 10:
        return '+1' + digits
    if len(digits) == 11 and digits.startswith('1'):
        return '+' + digits
    return digits


class SignalWireOutboundController(http.Controller):

    def _cxml(self, body):
        return request.make_response(
            f'<?xml version="1.0" encoding="UTF-8"?><Response>{body}</Response>',
            headers=[('Content-Type', 'text/xml')])

    @http.route('/signalwire/voice/outbound', type='http', auth='public', methods=['POST'], csrf=False)
    @signalwire_signed
    def outbound_call(self, **kwargs):
        _logger.info("SignalWire outbound call request: %s",
                     {k: v for k, v in kwargs.items() if k not in ('AccountSid', 'ApiVersion')})
        username = sip_user(kwargs.get('From'))
        user = request.env['res.users'].sudo().search([('voip_username', '=', username)], limit=1) \
            if username else request.env['res.users']
        if not user:
            _logger.warning("SignalWire outbound call from an unknown phone %r: refused.", kwargs.get('From'))
            return self._cxml('<Reject/>')
        number = dialed_number(kwargs.get('To'))
        if not number:  # another phone on the account: ring it as before
            target = saxutils.escape((kwargs.get('To') or '').strip('<>'))
            return self._cxml(f'<Dial><Sip>{target}</Sip></Dial>')
        settings = user._signalwire_outbound_settings()
        caller_id = settings.get('send_as')
        if not caller_id:  # same rule as on the phone: no E911, no outside calls
            return self._cxml(
                '<Say>Outside calls need an emergency address on your number first. '
                'Please ask your administrator.</Say><Hangup/>')
        return self._cxml(
            f'<Dial callerId="{saxutils.escape(caller_id)}"><Number>{saxutils.escape(number)}</Number></Dial>')
