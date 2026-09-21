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

    def _group_sip_targets(self, group, sip_domain):
        return ''.join(self._sip_targets(member, sip_domain) for member in group.member_ids)

    def _voicemail_cxml(self, user, voicemail_action, transcribe_action=None):
        """The <Say>+<Record> block used both by a user's own personal
        fallback chain and by an unanswered call group's voicemail
        target - factored out so both call sites build the exact same
        shape rather than drifting apart over time.
        """
        record_attrs = f'action="{voicemail_action}" maxLength="120" playBeep="true"'
        if user.signalwire_voicemail_transcribe and transcribe_action:
            record_attrs = (
                f'action="{voicemail_action}?transcribe=1" maxLength="120" playBeep="true" '
                f'transcribe="true" transcribeCallback="{transcribe_action}"')
        return (
            '<Say>Please leave a message after the tone.</Say>'
            f'<Record {record_attrs} />')

    def _user_voicemail_cxml(self, user, number):
        """A user's own personal voicemail box, addressed by user_id/
        phone_number_id the same way the fallback chain's own
        voicemail step reaches it - reused by an IVR menu option
        set to "Take a Voicemail" so both routes into the exact same
        signalwire.voicemail-creating webhook.
        """
        voicemail_action = f'/signalwire/voice/voicemail_complete/{user.id}/{number.id}'
        transcribe_action = (
            f'/signalwire/voice/voicemail_transcription/{user.id}/{number.id}'
            if user.signalwire_voicemail_transcribe else None)
        return self._voicemail_cxml(user, voicemail_action, transcribe_action)

    def _route_dial_cxml(self, route_type, target, number, sip_domain):
        """The <Dial> block for a resolved 'user' or 'group' route -
        shared by inbound_call's own initial dial and an IVR menu
        option set to "Ring a User"/"Ring a Call Group", so both
        build the exact same shape (same timeout, same fallback
        action wiring) rather than drifting apart. Returns '' if the
        route has no usable SIP target at all.
        """
        if route_type == 'group':
            targets = self._group_sip_targets(target, sip_domain) if target else ''
            if not targets:
                return ''
            action = f'/signalwire/voice/group_fallback/{target.id}/{number.id}'
        else:
            targets = self._sip_targets(target, sip_domain) if target else ''
            if not targets:
                return ''
            action = f'/signalwire/voice/fallback/{target.id}/{number.id}'
        return f'<Dial timeout="{DIAL_TIMEOUT}" action="{action}">{targets}</Dial>'

    def _ivr_menu_cxml(self, menu, number):
        """The <Gather> prompt for `menu` - a re-prompt if the caller
        presses nothing or an unrecognized digit falls through to
        the same <Say>+<Hangup> tail after the <Gather> itself times
        out without a match (standard Twilio-compatible <Gather>
        behavior: falling through to whatever cXML follows it).
        """
        digit_action = f'/signalwire/voice/ivr/{menu.id}/{number.id}/digit'
        greeting = saxutils.escape(menu.greeting_text or '')
        return (
            f'<Gather numDigits="1" timeout="5" action="{digit_action}">'
            f'<Say>{greeting}</Say>'
            '</Gather>'
            '<Say>We did not receive a selection. Goodbye.</Say>'
            '<Hangup/>')

    @http.route(
        '/signalwire/voice/inbound', type='http', auth='public',
        methods=['POST'], csrf=False)
    def inbound_call(self, **kwargs):
        """SignalWire POSTs standard Twilio-compatible form fields
        here on every inbound call to any number whose Voice URL
        points here - looked up by the call's To field, same one-
        webhook-for-every-number convention as the SMS inbound
        webhook. Resolves the number's own effective route (a user, a
        Call Group, or an IVR Menu - swapped for an After-Hours
        target instead if a Business Hours calendar is set and now
        falls outside it - see
        signalwire.phone_number._effective_route()). A user route
        falls through to that user's own personal fallback chain
        (forward/ring group/voicemail) if unanswered; a group route
        falls through to group_fallback instead; an IVR route hands
        the caller a menu with no timeout-driven fallback of its own.
        """
        to_number = request.httprequest.form.get('To', '')
        number = request.env['signalwire.phone_number'].sudo().search(
            [('name', '=', to_number)], limit=1)
        if not number:
            return self._cxml('<Reject/>')

        route_type, target = number._effective_route()

        if route_type == 'ivr':
            if not target:
                return self._cxml('<Reject/>')
            return self._cxml(self._ivr_menu_cxml(target, number))

        sip_domain = number.subproject_id.server_id._get_sip_domain()
        dial = self._route_dial_cxml(route_type, target, number, sip_domain)
        if not dial:
            return self._cxml('<Reject/>')
        return self._cxml(dial)

    @http.route(
        '/signalwire/voice/group_fallback/<int:group_id>/<int:phone_number_id>',
        type='http', auth='public', methods=['POST'], csrf=False)
    def group_fallback(self, group_id, phone_number_id, **kwargs):
        """Called after a Call Group's own <Dial> ends unanswered.
        Routes to the group's own voicemail_user_id's voicemail box if
        one is set, otherwise ends the call with a plain apology -
        deliberately not a full per-user fallback chain (forward/ring
        group/voicemail) the way a direct user route gets, since a
        group has no single natural owner for that chain.
        """
        status = request.httprequest.form.get('DialCallStatus')
        if status == 'completed':
            return self._cxml('')

        group = request.env['signalwire.call.group'].sudo().browse(group_id)
        number = request.env['signalwire.phone_number'].sudo().browse(phone_number_id)
        if not group.exists() or not number.exists():
            return self._cxml('<Reject/>')

        voicemail_user = group.voicemail_user_id
        if not voicemail_user:
            return self._cxml('<Say>Sorry, no one is available to take your call.</Say>')

        return self._cxml(self._user_voicemail_cxml(voicemail_user, number))

    @http.route(
        '/signalwire/voice/ivr/<int:menu_id>/<int:phone_number_id>',
        type='http', auth='public', methods=['POST'], csrf=False)
    def ivr_menu(self, menu_id, phone_number_id, **kwargs):
        """Entry point for an IVR Menu - also re-entered for a
        "Go to Another Menu" option's own submenu, and for a re-prompt
        after an invalid digit (see ivr_digit below).
        """
        menu = request.env['signalwire.ivr.menu'].sudo().browse(menu_id)
        number = request.env['signalwire.phone_number'].sudo().browse(phone_number_id)
        if not menu.exists() or not number.exists():
            return self._cxml('<Reject/>')
        return self._cxml(self._ivr_menu_cxml(menu, number))

    @http.route(
        '/signalwire/voice/ivr/<int:menu_id>/<int:phone_number_id>/digit',
        type='http', auth='public', methods=['POST'], csrf=False)
    def ivr_digit(self, menu_id, phone_number_id, **kwargs):
        """Handles the digit a caller pressed in response to
        ivr_menu's own <Gather>. An unrecognized digit re-prompts the
        same menu rather than rejecting the call outright - a caller
        who fat-fingers a digit shouldn't have to call back.
        """
        digit = request.httprequest.form.get('Digits', '')
        menu = request.env['signalwire.ivr.menu'].sudo().browse(menu_id)
        number = request.env['signalwire.phone_number'].sudo().browse(phone_number_id)
        if not menu.exists() or not number.exists():
            return self._cxml('<Reject/>')

        option = menu.option_ids.filtered(lambda o: o.digit == digit)[:1]
        if not option:
            return self._cxml(
                '<Say>Sorry, that is not a valid option.</Say>'
                + self._ivr_menu_cxml(menu, number))

        if option.action_type == 'hangup':
            return self._cxml('<Hangup/>')
        if option.action_type == 'submenu':
            if not option.target_submenu_id:
                return self._cxml('<Reject/>')
            return self._cxml(self._ivr_menu_cxml(option.target_submenu_id, number))
        if option.action_type == 'voicemail':
            if not option.target_user_id:
                return self._cxml('<Reject/>')
            return self._cxml(self._user_voicemail_cxml(option.target_user_id, number))
        if option.action_type == 'group':
            sip_domain = number.subproject_id.server_id._get_sip_domain()
            dial = self._route_dial_cxml(
                'group', option.target_call_group_id, number, sip_domain)
            return self._cxml(dial or '<Reject/>')

        # action_type == 'user'
        sip_domain = number.subproject_id.server_id._get_sip_domain()
        dial = self._route_dial_cxml('user', option.target_user_id, number, sip_domain)
        return self._cxml(dial or '<Reject/>')

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
            return self._cxml(self._user_voicemail_cxml(user, number))

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
