# -*- coding: utf-8 -*-
import logging

import requests

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

CXML_HEADER = '<?xml version="1.0" encoding="UTF-8"?>'
DIAL_TIMEOUT = 20

# The fallback chain, in order - "softphone" itself isn't in this list
# since it's always the implicit first attempt, made directly by
# inbound_call rather than by _next_step.
STEP_ORDER = ['forward', 'group', 'voicemail']


class SignalWireVoiceController(http.Controller):

    def _cxml(self, body):
        return request.make_response(
            f'{CXML_HEADER}<Response>{body}</Response>',
            headers=[('Content-Type', 'text/xml')])

    def _next_step(self, user, after=None):
        """The next fallback step actually configured for `user`,
        after the one named `after` (or from the very start if
        `after` is None) - skips any step that isn't set up, so a
        user who's only enabled voicemail goes straight there instead
        of stalling on an unconfigured forward/group step.
        """
        steps = STEP_ORDER
        if after:
            steps = steps[steps.index(after) + 1:]
        for step in steps:
            if step == 'forward' and user.signalwire_active_forward_id:
                return 'forward'
            if step == 'group' and user.signalwire_ring_group_ids.filtered('voip_username'):
                return 'group'
            if step == 'voicemail' and user.signalwire_voicemail_enabled:
                return 'voicemail'
        return None

    @http.route(
        '/signalwire/voice/inbound', type='http', auth='public',
        methods=['POST'], csrf=False)
    def inbound_call(self, **kwargs):
        """SignalWire POSTs standard Twilio-compatible form fields
        here on every inbound call to any number whose Voice URL
        points here - looked up by the call's To field, same one-
        webhook-for-every-number convention as the SMS inbound
        webhook. Always tries the assigned user's own softphone
        first; a User-configured fallback chain (forward/ring group/
        voicemail - see res.users' own fields) only kicks in from
        here on if that doesn't get answered within DIAL_TIMEOUT.
        """
        to_number = request.httprequest.form.get('To', '')
        number = request.env['signalwire.phone_number'].sudo().search(
            [('name', '=', to_number)], limit=1)
        user = number.assigned_user_id if number else request.env['res.users']

        if not number or not user or not user.voip_username:
            return self._cxml('<Reject/>')

        sip_domain = number.subproject_id.server_id._get_sip_domain()
        action = f'/signalwire/voice/fallback/{user.id}/{number.id}'
        dial = (
            f'<Dial timeout="{DIAL_TIMEOUT}" action="{action}">'
            f'<Sip>sip:{user.voip_username}@{sip_domain}</Sip></Dial>'
        )
        return self._cxml(dial)

    @http.route(
        '/signalwire/voice/fallback/<int:user_id>/<int:phone_number_id>',
        type='http', auth='public', methods=['POST'], csrf=False)
    def fallback(self, user_id, phone_number_id, step=None, **kwargs):
        """Called after ANY <Dial> attempt in the chain ends - the
        softphone itself, or a previous fallback step. `step` names
        which step just finished (blank the very first time, meaning
        the softphone attempt itself just ended) - not which step to
        run now; _next_step figures that out from what's actually
        configured.
        """
        status = request.httprequest.form.get('DialCallStatus')
        if status == 'completed':
            # Was actually answered somewhere in the chain, and the
            # call already ended normally - nothing more to do.
            return self._cxml('')

        user = request.env['res.users'].sudo().browse(user_id)
        number = request.env['signalwire.phone_number'].sudo().browse(phone_number_id)
        if not user.exists() or not number.exists():
            return self._cxml('<Reject/>')

        next_step = self._next_step(user, after=step)
        action = f'/signalwire/voice/fallback/{user.id}/{number.id}?step={next_step}'

        if next_step == 'forward':
            target = user.signalwire_active_forward_id.phone_number
            return self._cxml(
                f'<Dial timeout="{DIAL_TIMEOUT}" action="{action}">'
                f'<Number>{target}</Number></Dial>')

        if next_step == 'group':
            sip_domain = number.subproject_id.server_id._get_sip_domain()
            teammates = user.signalwire_ring_group_ids.filtered('voip_username')
            sips = ''.join(
                f'<Sip>sip:{teammate.voip_username}@{sip_domain}</Sip>'
                for teammate in teammates)
            return self._cxml(
                f'<Dial timeout="{DIAL_TIMEOUT}" action="{action}">{sips}</Dial>')

        if next_step == 'voicemail':
            voicemail_action = f'/signalwire/voice/voicemail_complete/{user.id}/{number.id}'
            return self._cxml(
                '<Say>Please leave a message after the tone.</Say>'
                f'<Record action="{voicemail_action}" maxLength="120" playBeep="true" />')

        return self._cxml('<Reject/>')

    @http.route(
        '/signalwire/voice/voicemail_complete/<int:user_id>/<int:phone_number_id>',
        type='http', auth='public', methods=['POST'], csrf=False)
    def voicemail_complete(self, user_id, phone_number_id, **kwargs):
        form = request.httprequest.form
        recording_url = form.get('RecordingUrl')
        duration = int(form.get('RecordingDuration') or 0)
        from_number = form.get('From', '')

        user = request.env['res.users'].sudo().browse(user_id)
        number = request.env['signalwire.phone_number'].sudo().browse(phone_number_id)
        if not user.exists() or not number.exists():
            return self._cxml('<Hangup/>')

        attachment = request.env['ir.attachment'].sudo()
        if recording_url:
            server = number.subproject_id.server_id
            try:
                resp = requests.get(
                    f'{recording_url}.mp3',
                    auth=(server.project_id, server.api_token), timeout=30)
                if resp.ok:
                    attachment = attachment.create({
                        'name': f'Voicemail from {from_number}.mp3',
                        'type': 'binary', 'raw': resp.content, 'mimetype': 'audio/mpeg',
                    })
            except requests.RequestException:
                _logger.exception(
                    "SignalWire: could not fetch voicemail recording for user %s", user_id)

        partner = user._signalwire_match_partner(from_number)
        voicemail = request.env['signalwire.voicemail'].sudo().create({
            'phone_number_id': number.id,
            'user_id': user.id,
            'from_number': from_number,
            'duration': duration,
            'recording_attachment_id': attachment.id or False,
            'partner_id': partner.id if partner else False,
        })
        voicemail._log_and_notify()

        return self._cxml('<Hangup/>')
