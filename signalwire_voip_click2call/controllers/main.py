# -*- coding: utf-8 -*-
import logging
import re
from xml.sax import saxutils

import requests

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

CXML_HEADER = '<?xml version="1.0" encoding="UTF-8"?>'
DIAL_TIMEOUT = 20

# Matches a desk phone's own provisioning filename patterns - see
# signalwire.desk_phone._provisioning_path for where these are built.
YEALINK_FILENAME_RE = re.compile(r'^([0-9a-f]{12})\.cfg$')
GRANDSTREAM_FILENAME_RE = re.compile(r'^cfg([0-9a-f]{12})\.xml$')

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
            if step == 'group' and any(
                    teammate.voip_username or teammate.signalwire_desk_phone_ids.filtered(
                        'voip_username')
                    for teammate in user.signalwire_ring_group_ids):
                return 'group'
            if step == 'voicemail' and user.signalwire_voicemail_enabled:
                return 'voicemail'
        return None

    def _sip_targets(self, user, sip_domain):
        """Every SIP URI that should ring for `user` right now - their
        own softphone (if provisioned) plus any of their own desk
        phones (each its own separate SIP Endpoint, rung together via
        this single <Dial>'s multiple <Sip> children rather than
        relying on multi-registration on one shared endpoint).
        """
        usernames = [user.voip_username] if user.voip_username else []
        usernames += user.signalwire_desk_phone_ids.filtered('voip_username').mapped(
            'voip_username')
        return ''.join(f'<Sip>sip:{username}@{sip_domain}</Sip>' for username in usernames)

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

        sip_domain = number.subproject_id.server_id._get_sip_domain() if number else False
        targets = self._sip_targets(user, sip_domain) if number and user else ''
        if not number or not user or not targets:
            return self._cxml('<Reject/>')

        action = f'/signalwire/voice/fallback/{user.id}/{number.id}'
        dial = f'<Dial timeout="{DIAL_TIMEOUT}" action="{action}">{targets}</Dial>'
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
            sips = ''.join(
                self._sip_targets(teammate, sip_domain)
                for teammate in user.signalwire_ring_group_ids)
            return self._cxml(
                f'<Dial timeout="{DIAL_TIMEOUT}" action="{action}">{sips}</Dial>')

        if next_step == 'voicemail':
            voicemail_action = f'/signalwire/voice/voicemail_complete/{user.id}/{number.id}'
            record_attrs = f'action="{voicemail_action}" maxLength="120" playBeep="true"'
            if user.signalwire_voicemail_transcribe:
                voicemail_action += '?transcribe=1'
                transcribe_action = (
                    f'/signalwire/voice/voicemail_transcription/{user.id}/{number.id}')
                record_attrs = (
                    f'action="{voicemail_action}" maxLength="120" playBeep="true" '
                    f'transcribe="true" transcribeCallback="{transcribe_action}"')
            return self._cxml(
                '<Say>Please leave a message after the tone.</Say>'
                f'<Record {record_attrs} />')

        return self._cxml('<Reject/>')

    @http.route(
        '/signalwire/voice/voicemail_complete/<int:user_id>/<int:phone_number_id>',
        type='http', auth='public', methods=['POST'], csrf=False)
    def voicemail_complete(self, user_id, phone_number_id, transcribe=None, **kwargs):
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
            'recording_url': recording_url or False,
            'partner_id': partner.id if partner else False,
            'transcription_status': 'pending' if transcribe == '1' else 'none',
        })
        voicemail._log_and_notify()

        return self._cxml('<Hangup/>')

    @http.route(
        '/signalwire/voice/voicemail_transcription/<int:user_id>/<int:phone_number_id>',
        type='http', auth='public', methods=['POST'], csrf=False)
    def voicemail_transcription(self, user_id, phone_number_id, **kwargs):
        """SignalWire's own transcribeCallback webhook - fires
        asynchronously, well after the call itself has ended, so this
        isn't part of the live cXML call flow at all (no <Response>
        expected back). Its payload carries RecordingUrl but neither
        our own user_id/phone_number_id nor a CallSid (confirmed via
        SignalWire's docs), so RecordingUrl - stored on the voicemail
        record at creation time - is what correlates this callback
        back to the right row.
        """
        form = request.httprequest.form
        recording_url = form.get('RecordingUrl')
        status = form.get('TranscriptionStatus')
        text = form.get('TranscriptionText')

        voicemail = request.env['signalwire.voicemail'].sudo().search([
            ('user_id', '=', user_id), ('phone_number_id', '=', phone_number_id),
            ('recording_url', '=', recording_url),
        ], limit=1, order='create_date desc')
        if voicemail:
            voicemail._log_transcription(
                status if status in ('completed', 'failed') else 'failed', text)
        else:
            _logger.warning(
                "SignalWire: transcription callback for user %s matched no voicemail "
                "(RecordingUrl %s)", user_id, recording_url)

        return request.make_response('', headers=[('Content-Type', 'text/plain')])

    @http.route(
        '/signalwire/provisioning/<string:filename>',
        type='http', auth='public', methods=['GET'], csrf=False)
    def desk_phone_provisioning(self, filename, **kwargs):
        """Zero-touch config-file endpoint a physical desk phone
        fetches on boot, keyed by its own MAC address - either pasted
        in by hand as the phone's "Auto Provision Server URL", or
        reached automatically via a DHCP scope's option 66 (the phone
        appends its own filename on its own, matching one of the two
        patterns below - see signalwire.desk_phone._provisioning_path
        for where each is built).

        A MAC address isn't secret, so this deliberately accepts the
        same trust model every hosted-PBX provider's auto-provisioning
        uses: knowing/guessing a valid MAC gets that one phone's own
        SIP password, never anything account-wide - see this module's
        README for the tradeoff written out in full, not glossed over.
        """
        yealink_match = YEALINK_FILENAME_RE.match(filename)
        grandstream_match = GRANDSTREAM_FILENAME_RE.match(filename)
        if not (yealink_match or grandstream_match):
            return request.not_found()

        mac = (yealink_match or grandstream_match).group(1)
        phone = request.env['signalwire.desk_phone'].sudo().search(
            [('mac_address', '=', mac)], limit=1)
        if not phone or not phone.voip_username:
            _logger.warning(
                "SignalWire: provisioning request for an unknown or "
                "unprovisioned MAC address (%s)", mac)
            return request.not_found()

        sip_domain = phone.signalwire_server_id._get_sip_domain()
        if yealink_match:
            body = self._yealink_config(phone, sip_domain)
            content_type = 'text/plain'
        else:
            body = self._grandstream_config(phone, sip_domain)
            content_type = 'text/xml'
        return request.make_response(body, headers=[('Content-Type', content_type)])

    @staticmethod
    def _yealink_config(phone, sip_domain):
        return (
            "account.1.enable = 1\n"
            f"account.1.label = {phone.name}\n"
            f"account.1.display_name = {phone.name}\n"
            f"account.1.user_name = {phone.voip_username}\n"
            f"account.1.auth_name = {phone.voip_username}\n"
            f"account.1.password = {phone.voip_password}\n"
            f"account.1.sip_server.1.address = {sip_domain}\n"
            "account.1.sip_server.1.port = 5060\n"
        )

    @staticmethod
    def _grandstream_config(phone, sip_domain):
        name = saxutils.escape(phone.name or '')
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<gs_provision version="1">\n'
            '<config version="1">\n'
            '<P271>1</P271>\n'
            f'<P270>{name}</P270>\n'
            f'<P35>{phone.voip_username}</P35>\n'
            f'<P36>{phone.voip_username}</P36>\n'
            f'<P34>{phone.voip_password}</P34>\n'
            f'<P47>{sip_domain}</P47>\n'
            '</config>\n'
            '</gs_provision>\n'
        )
