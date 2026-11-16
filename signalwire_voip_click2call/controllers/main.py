# -*- coding: utf-8 -*-
import logging
import re
from xml.sax import saxutils

import requests
import werkzeug.urls

from odoo import fields, http
from odoo.http import request

from odoo.addons.signalwire_voip.webhook_security import signalwire_signed

from ..models.signalwire_live_call import (
    FINISHED_STATUSES, OFFER_TIMEOUT, OFFER_TIMEOUT_MOBILE)

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
                    teammate.signalwire_presence != 'away' and (
                        teammate.voip_username or teammate.signalwire_desk_phone_ids.filtered(
                            'voip_username'))
                    for teammate in user.signalwire_ring_group_ids):
                return 'group'
            if step == 'voicemail' and user.signalwire_voicemail_enabled:
                return 'voicemail'
        return None

    def _sip_targets(self, user, sip_domain, ignore_presence=False):
        """Every SIP URI that should ring for `user` right now - their
        own softphone (if provisioned) plus any of their own desk
        phones (each its own separate SIP Endpoint, rung together via
        this single <Dial>'s multiple <Sip> children rather than
        relying on multi-registration on one shared endpoint).
        """
        presence = 'available' if ignore_presence else user.signalwire_presence
        if presence == 'away':
            return ''
        usernames = [user.voip_username] if user.voip_username else []
        if presence == 'available':
            # Desk phones only ring while they're at their desk.
            usernames += user.signalwire_desk_phone_ids.filtered('voip_username').mapped(
                'voip_username')
        attrs = self._answered_callback_attrs(user)
        targets = ''.join(
            f'<Sip{attrs}>sip:{username}@{sip_domain}</Sip>' for username in usernames)
        mobile = user.signalwire_mobile_forward_id.phone_number
        if presence == 'mobile' and mobile:
            targets += f'<Number{attrs} url={self._screen_url(user)}>{saxutils.escape(mobile)}</Number>'
        return targets

    def _screen_url(self, user):
        """The quoted url= for a mobile leg: SignalWire fetches it when the
        mobile answers, and only connects the caller after a 1 is pressed,
        so the mobile's own voicemail can't take the call."""
        base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
        caller = request.httprequest.form.get('From', '')
        url = f'{base_url}/signalwire/voice/screen/{user.id}'
        if caller:
            url += '?' + werkzeug.urls.url_encode({'caller': caller})
        return saxutils.quoteattr(url)

    def _answered_callback_attrs(self, user):
        """Asks SignalWire to tell us when this leg is answered, so the
        live call shows Connected (and who took it) instead of Ringing."""
        base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return (
            ' statusCallbackEvent="answered" statusCallbackMethod="POST"'
            f' statusCallback="{base_url}/signalwire/voice/leg_answered/{user.id}"')

    def _group_sip_targets(self, group, sip_domain):
        return ''.join(self._sip_targets(member, sip_domain) for member in group.member_ids)

    DEFAULT_VOICEMAIL_GREETING = 'Please leave a message after the tone.'
    DEFAULT_HOLD_MESSAGE = 'Please hold while we connect you.'
    DEFAULT_GROUP_HOLD_MESSAGE = 'Please hold while we try to reach someone.'

    def _say(self, text):
        """A plain <Say> tag (SignalWire's own built-in voice),
        escaping `text` - always user-entered, never trusted markup.
        """
        return f'<Say>{saxutils.escape(text or "")}</Say>'

    def _say_or_play(self, text, piper_voice, piper_speaker_id=None):
        """The same spoken content as _say(), but via a self-hosted
        Piper voice instead of SignalWire's own built-in one, if
        `piper_voice` is set and audio for this exact (voice, speaker,
        text) triple is already cached - `signalwire_piper_tts`
        (optional, may not be installed) is the only thing that ever
        populates that cache, and only ever does so eagerly, when a
        greeting's own text/voice is saved, never from here. This
        method never calls Piper itself and never blocks a live call
        on it being up - no cached audio (Piper not installed/
        configured, or the one synthesis attempt for this text
        failed) always falls back to the plain _say() above.

        `piper_speaker_id` arrives as a Selection field's own string
        value (e.g. "42", one owner model's real speaker picker) -
        cast to int here, once, so every call site can just pass the
        raw field value through and every cache lookup/hash agrees on
        the type (signalwire.piper.audio.cache's own sync side casts
        the same way - see each owner model's _sync_piper_audio).
        """
        speaker_id = int(piper_speaker_id) if piper_speaker_id else None
        if piper_voice and 'signalwire.piper.audio.cache' in request.env:
            attachment = request.env['signalwire.piper.audio.cache'].sudo().get_cached(
                piper_voice, text, speaker_id)
            if attachment:
                base_url = request.env['ir.config_parameter'].sudo().get_param(
                    'web.base.url')
                return (
                    f'<Play>{base_url}/signalwire/voice/piper_audio/'
                    f'{attachment.id}</Play>')
        return self._say(text)

    def _voicemail_cxml(
            self, voicemail_action, transcribe_action=None,
            greeting_attachment=None, greeting_text=None,
            max_length=120, beep=True, piper_voice=None, piper_speaker_id=None):
        """The <Say>/<Play>+<Record> block used both by a user's own
        personal fallback chain and by an unanswered call group's
        voicemail target - factored out so both call sites build the
        exact same shape rather than drifting apart over time. Takes
        already-resolved settings rather than a res.users record, so
        it works equally for a group's own mailbox (see
        _group_voicemail_cxml).
        """
        if greeting_attachment:
            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
            greeting = f'<Play>{base_url}/signalwire/voice/greeting/{greeting_attachment.id}</Play>'
        else:
            text = greeting_text or self.DEFAULT_VOICEMAIL_GREETING
            greeting = self._say_or_play(text, piper_voice, piper_speaker_id)
        beep_attr = 'true' if beep else 'false'
        record_attrs = f'action="{voicemail_action}" maxLength="{max_length}" playBeep="{beep_attr}"'
        if transcribe_action:
            record_attrs = (
                f'action="{voicemail_action}?transcribe=1" maxLength="{max_length}" '
                f'playBeep="{beep_attr}" transcribe="true" '
                f'transcribeCallback="{transcribe_action}"')
        return f'{greeting}<Record {record_attrs} />'

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
        greeting_attachment = request.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'res.users'), ('res_id', '=', user.id),
            ('res_field', '=', 'signalwire_voicemail_greeting'),
        ], limit=1)
        return self._voicemail_cxml(
            voicemail_action, transcribe_action,
            greeting_attachment=greeting_attachment,
            greeting_text=user.signalwire_voicemail_greeting_text,
            max_length=user.signalwire_voicemail_max_length,
            beep=user.signalwire_voicemail_beep,
            piper_voice=getattr(user, 'signalwire_voicemail_piper_voice', False),
            piper_speaker_id=getattr(user, 'signalwire_voicemail_piper_speaker_id', False))

    def _group_voicemail_cxml(self, group, number):
        """A call group's own shared mailbox - has its own greeting
        (custom recording or text), but still uses the generic
        default max length/beep rather than any one member's own
        settings (a group has no single natural owner to pull those
        from, same reasoning signalwire.call.group's own docstring
        gives for not building it a full personal fallback chain).
        """
        voicemail_action = f'/signalwire/voice/group_voicemail_complete/{group.id}/{number.id}'
        greeting_attachment = request.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'signalwire.call.group'), ('res_id', '=', group.id),
            ('res_field', '=', 'voicemail_greeting'),
        ], limit=1)
        return self._voicemail_cxml(
            voicemail_action,
            greeting_attachment=greeting_attachment,
            greeting_text=getattr(group, 'voicemail_greeting_text', False),
            piper_voice=getattr(group, 'voicemail_piper_voice', False),
            piper_speaker_id=getattr(group, 'voicemail_piper_speaker_id', False))

    def _route_dial_cxml(self, route_type, target, number, sip_domain, attempt=0,
                         ignore_presence=False):
        """The <Dial> block for a resolved 'user' or 'group' route -
        shared by inbound_call's own initial dial and an IVR menu
        option set to "Ring a User"/"Ring a Call Group", so both
        build the exact same shape (same timeout, same fallback
        action wiring) rather than drifting apart. Returns '' if the
        route has no usable SIP target at all.

        `attempt` is only meaningful for a 'group' route - a nonzero
        value means this is a hold-and-retry re-ring (see
        group_fallback), carried through as a query-string param on
        the action URL so group_fallback knows how many attempts have
        already happened. Left at 0/omitted, the action URL is byte-
        for-byte identical to before this parameter existed.
        """
        if route_type == 'group':
            targets = self._group_sip_targets(target, sip_domain) if target else ''
            if not targets:
                return ''
            action = f'/signalwire/voice/group_fallback/{target.id}/{number.id}'
            if attempt:
                action += f'?attempt={attempt}'
        else:
            targets = self._sip_targets(
                target, sip_domain, ignore_presence=ignore_presence) if target else ''
            if not targets:
                return ''
            action = f'/signalwire/voice/fallback/{target.id}/{number.id}'
        return f'<Dial timeout="{DIAL_TIMEOUT}" action="{action}">{targets}</Dial>'

    def _hold_cxml(self, record, default_message, res_model, offer=''):
        """The spoken hold message (via _say_or_play, so an optional
        Piper voice is honored the same way a greeting's is) followed
        by looped hold music if `record.hold_music` is set, or a
        short pause otherwise - the shared building block for both
        hold_loop's own indefinite self-redirecting loop and
        group_fallback's fixed-length cycle before a fresh ring
        attempt. `res_model` scopes the music attachment lookup the
        same way _user_voicemail_cxml/_group_voicemail_cxml do for
        greetings - never an open-ended attachment-id fetch.
        """
        message = self._say_or_play(
            record.hold_message_text or default_message,
            getattr(record, 'hold_piper_voice', False),
            getattr(record, 'hold_piper_speaker_id', False))
        music_attachment = request.env['ir.attachment'].sudo().search([
            ('res_model', '=', res_model), ('res_id', '=', record.id),
            ('res_field', '=', 'hold_music'),
        ], limit=1)
        if music_attachment:
            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
            return (
                f'{message}{offer}<Play loop="3">{base_url}/signalwire/voice/'
                f'hold_music/{music_attachment.id}</Play>')
        return f'{message}{offer}<Pause length="20" />'

    CALLBACK_OFFER = 'To be called back instead, press 1 at any time.'
    CALLBACK_CONFIRM = (
        'Thank you. We will call you back at the number you are calling from. Goodbye.')

    def _hold_with_callback_offer(self, record, default_message, res_model, kind, target,
                                  number, attempt=0):
        """The hold message and music, inside a <Gather> that takes a 1 as
        "call me back instead" (callback_offer). Not offered when the
        caller's number is withheld: there'd be nothing to call back. No
        key pressed: the hold ends and the call carries on exactly as
        before (a <Gather> without input falls through to what follows)."""
        caller_digits = re.sub(r'\D', '', request.httprequest.form.get('From', ''))
        if len(caller_digits) < 7:
            return self._hold_cxml(record, default_message, res_model)
        offer = self._say_or_play(
            self.CALLBACK_OFFER, getattr(record, 'hold_piper_voice', False),
            getattr(record, 'hold_piper_speaker_id', False))
        hold = self._hold_cxml(record, default_message, res_model, offer=offer)
        action = (f'/signalwire/voice/callback_offer/{kind}/'
                  f'{target.id if target else 0}/{number.id}')
        if attempt:
            action += f'?attempt={attempt}'
        return f'<Gather numDigits="1" timeout="1" action="{saxutils.escape(action)}">{hold}</Gather>'

    def _mark_live_call_ended(self):
        """Called from every terminal point in the routing chain
        (answered-and-done, voicemail, or rejected) - CallSid is
        present on every one of SignalWire's own webhook POSTs for a
        call, not just the first, so this can be called generically
        rather than needing the id threaded through every route.
        """
        call_sid = request.httprequest.form.get('CallSid', '')
        if call_sid:
            request.env['signalwire.live_call'].sudo().search(
                [('call_sid', '=', call_sid), ('state', '!=', 'ended')]
            ).write({'state': 'ended'})

    def _nobody_to_ring_cxml(self, route_type, target, number):
        """No phone to ring: someone set to Away goes straight to what
        happens when they don't answer, an all-Away group to its
        voicemail; anything else (nobody set up) is rejected as before."""
        if route_type == 'user' and target and target.signalwire_presence == 'away':
            return self._user_fallback_cxml(target, number)
        if route_type == 'group' and target and target.member_ids.filtered(
                lambda m: m.signalwire_presence == 'away'):
            return self._group_unanswered_cxml(target, number)
        return self._dead_end_cxml(number)

    def _caller_has_number(self):
        return len(re.sub(r'\D', '', request.httprequest.form.get('From', ''))) >= 7

    def _dead_end_cxml(self, number=None):
        """Nothing is set up to take this call. Never a busy/rejected tone
        for a real caller: say so, and (with caller ID) leave a "missed
        call" callback request for the receptionist panel."""
        self._mark_live_call_ended()
        number = number.exists() if number else number
        if not number:
            return self._cxml('<Reject/>')  # not one of our numbers
        body = self._say("Sorry, we couldn't connect your call.")
        if self._caller_has_number():
            caller = request.httprequest.form.get('From', '')
            request.env['signalwire.callback_request'].sudo().create({
                'source': 'phone', 'phone_number': caller,
                'partner_id': request.env['res.users'].sudo()._signalwire_match_partner(
                    caller).id or False,
                'note': 'Missed call: nobody was set up to take it.',
                'company_id': number.company_id.id or request.env.company.id,
            })
            body += self._say("We will call you back at the number you are calling from. Goodbye.")
        else:
            body += self._say('Please try again later. Goodbye.')
        return self._cxml(body + '<Hangup/>')

    # ---- queues ------------------------------------------------------

    QUEUE_OPTIONS = 'To be called back instead, press 1. To leave a message, press 2. Or stay on the line.'
    QUEUE_OPTIONS_NO_CALLBACK = 'To leave a message, press 2. Or stay on the line.'
    QUEUE_OPTIONS_CALLBACK_ONLY = 'To be called back instead, press 1. Or stay on the line.'

    def _live_call_for_request(self, number):
        """The live call for the call this webhook is about (made if the
        inbound webhook somehow didn't)."""
        form = request.httprequest.form
        LiveCall = request.env['signalwire.live_call'].sudo()
        call = LiveCall.search([('call_sid', '=', form.get('CallSid', ''))], limit=1)
        if not call:
            call = LiveCall.create({
                'call_sid': form.get('CallSid') or f'unknown-{fields.Datetime.now()}',
                'phone_number_id': number.id, 'from_number': form.get('From', '')})
        return call

    def _queue_mailbox(self, call):
        """(kind, owner) of the voicemail press 2 leads to, or (None, None)."""
        if call.queue_user_id:
            user = call.queue_user_id
            return ('user', user) if user.signalwire_voicemail_enabled else (None, None)
        group = call.queue_group_id
        if group.voicemail_mode == 'user' and group.voicemail_user_id:
            return 'user', group.voicemail_user_id
        if group.voicemail_mode == 'group':
            return 'group', group
        return None, None

    def _queue_offer_dial_cxml(self, call, agent):
        number = call.phone_number_id
        sip_domain = number.subproject_id.server_id._get_sip_domain()
        targets = self._sip_targets(agent, sip_domain)
        if not targets:
            call._queue_offer_missed()
            return self._queue_wait_cxml(call)
        timeout = OFFER_TIMEOUT_MOBILE if agent.signalwire_presence == 'mobile' else OFFER_TIMEOUT
        return (f'<Dial timeout="{timeout}" action="/signalwire/voice/queue_result/{call.id}">'
                f'{targets}</Dial>')

    def _queue_wait_cxml(self, call, turn=0):
        """One turn of waiting: where they are in line (every other turn),
        the hold message, the options, the music; then round again."""
        record = call.queue_group_id if call.queue_group_id and not call.queue_user_id \
            else call.phone_number_id
        res_model = record._name
        voice = (getattr(record, 'hold_piper_voice', False),
                 getattr(record, 'hold_piper_speaker_id', False))
        position = call._queue_position()
        intro = ''
        if turn % 2 == 0:
            intro = self._say_or_play(
                'You are next in line.' if position == 1
                else f'You are caller number {position} in line.', *voice)
        callback = self._caller_has_number()
        mailbox = self._queue_mailbox(call)[0]
        options_text = (self.QUEUE_OPTIONS if callback and mailbox
                        else self.QUEUE_OPTIONS_CALLBACK_ONLY if callback
                        else self.QUEUE_OPTIONS_NO_CALLBACK if mailbox else '')
        options = self._say_or_play(options_text, *voice) if options_text else ''
        hold = self._hold_cxml(record, self.DEFAULT_HOLD_MESSAGE, res_model, offer=options)
        again = f'/signalwire/voice/queue_wait/{call.id}?turn={turn + 1}'
        return (f'<Gather numDigits="1" timeout="1" action="/signalwire/voice/queue_choice/{call.id}">'
                f'{intro}{hold}</Gather><Redirect>{saxutils.escape(again)}</Redirect>')

    def _queue_join_cxml(self, number, group=None, user=None):
        """Situations 1 and 2: the caller joins a call group's queue or one
        person's own, and is offered at once to whoever is free the
        longest; if nobody is, they wait."""
        call = self._live_call_for_request(number)
        call._queue_join(group=group, user=user)
        agent = call._queue_try_offer()
        if agent:
            return self._cxml(self._queue_offer_dial_cxml(call, agent))
        # Someone was ahead of them: if an agent is free, the caller at the
        # front gets them; this one waits their turn.
        call._queue_dispatch_head()
        return self._cxml(self._queue_wait_cxml(call))

    def _person_is_busy(self, user):
        return bool(user) and user.signalwire_presence != 'away' and \
            user._signalwire_effective_call_state() in ('ringing', 'on_call')

    def _ivr_menu_cxml(self, menu, number):
        """The <Gather> prompt for `menu` - a re-prompt if the caller
        presses nothing or an unrecognized digit falls through to
        the same <Say>+<Hangup> tail after the <Gather> itself times
        out without a match (standard Twilio-compatible <Gather>
        behavior: falling through to whatever cXML follows it).
        """
        digit_action = f'/signalwire/voice/ivr/{menu.id}/{number.id}/digit'
        piper_voice = getattr(menu, 'piper_voice', False)
        piper_speaker_id = getattr(menu, 'piper_speaker_id', False)
        greeting = self._say_or_play(menu.greeting_text or '', piper_voice, piper_speaker_id)
        # This exact literal (not translated - matched byte-for-byte
        # against signalwire_voip_piper_tts's own eager-synthesis cache
        # key, if that module's installed; a translated string here
        # could silently never hit that cache) is duplicated in
        # signalwire_voip_piper_tts/models/signalwire_ivr_menu.py's own
        # IVR_NO_SELECTION_MESSAGE constant - keep them in sync.
        no_selection = self._say_or_play(
            'We did not receive a selection. Goodbye.', piper_voice, piper_speaker_id)
        return (
            f'<Gather numDigits="1" timeout="5" action="{digit_action}">'
            f'{greeting}'
            '</Gather>'
            f'{no_selection}'
            '<Hangup/>')

    @http.route(
        '/signalwire/voice/inbound', type='http', auth='public',
        methods=['POST'], csrf=False)
    @signalwire_signed
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
        the caller a menu with no timeout-driven fallback of its own;
        the two after-hours-only "straight to voicemail" routes skip
        ringing entirely.
        """
        to_number = request.httprequest.form.get('To', '')
        from_number = request.httprequest.form.get('From', '')
        call_sid = request.httprequest.form.get('CallSid', '')
        number = request.env['signalwire.phone_number'].sudo().search(
            [('name', '=', to_number)], limit=1)
        if not number:
            return self._cxml('<Reject/>')

        route_type, target = number._effective_route()

        if call_sid:
            request.env['signalwire.live_call'].sudo().create({
                'call_sid': call_sid, 'phone_number_id': number.id,
                'from_number': from_number,
                'assigned_user_id': target.id if route_type == 'user' else False,
            })

        if route_type == 'ivr':
            if not target:
                return self._dead_end_cxml(number)
            return self._cxml(self._ivr_menu_cxml(target, number))

        if route_type in ('user_voicemail', 'group_voicemail'):
            # An after-hours-only pair: skip ringing entirely (nobody's
            # actually expected to answer) and record a message right
            # away. _mark_live_call_ended() isn't called here - the
            # voicemail_complete/group_voicemail_complete webhook does
            # that itself once the recording actually finishes, same as
            # every other voicemail entry point in this controller.
            if not target:
                return self._dead_end_cxml(number)
            if route_type == 'user_voicemail':
                return self._cxml(self._user_voicemail_cxml(target, number))
            return self._cxml(self._group_voicemail_cxml(target, number))

        return self._ring_route_cxml(route_type, target, number)

    def _ring_route_cxml(self, route_type, target, number):
        """A number's or an IVR option's user/group route. A group: its
        queue (offered to whoever is free the longest). One person: rung
        as before, but if they're already on a call the caller waits in
        their personal queue instead of getting a busy line."""
        if route_type == 'group':
            if not target:
                return self._dead_end_cxml(number)
            return self._queue_join_cxml(number, group=target)
        if self._person_is_busy(target):
            return self._queue_join_cxml(number, user=target)
        sip_domain = number.subproject_id.server_id._get_sip_domain()
        dial = self._route_dial_cxml(route_type, target, number, sip_domain)
        if not dial:
            return self._nobody_to_ring_cxml(route_type, target, number)
        return self._cxml(dial)

    @http.route(
        '/signalwire/voice/group_fallback/<int:group_id>/<int:phone_number_id>',
        type='http', auth='public', methods=['POST'], csrf=False)
    @signalwire_signed
    def group_fallback(self, group_id, phone_number_id, attempt=None, **kwargs):
        """Called after a Call Group's own <Dial> ends unanswered.
        While `attempt` is still below the group's own
        max_ring_attempts, plays a hold message/music cycle and rings
        the whole group again instead of giving up immediately -
        `attempt` arrives as a query-string param on the action URL
        `_route_dial_cxml` builds, the same idiom `fallback`'s own
        `step` param uses for a user's fallback chain. Once attempts
        are exhausted (or max_ring_attempts is left at its default of
        0), routes to the group's own voicemail_mode exactly as
        before this parameter existed: a specific member's personal
        voicemail box, the group's own shared mailbox, or (if neither
        is set) just ends the call with a plain apology - deliberately
        not a full per-user fallback chain (forward/ring group/
        voicemail) the way a direct user route gets, since a group has
        no single natural owner for that chain.
        """
        status = request.httprequest.form.get('DialCallStatus')
        if status == 'completed':
            self._mark_live_call_ended()
            return self._cxml('')

        group = request.env['signalwire.call.group'].sudo().browse(group_id)
        number = request.env['signalwire.phone_number'].sudo().browse(phone_number_id)
        if not group.exists() or not number.exists():
            return self._dead_end_cxml(number)

        # Since 19.0.4.17.0 group calls go through the queue; this route
        # only still runs for calls that were ringing during the upgrade.
        return self._queue_join_cxml(number, group=group)

    def _group_unanswered_cxml(self, group, number):
        """Nobody in the group took the call (or everyone's Away): the
        group's own voicemail choice, or a plain apology."""
        if group.voicemail_mode == 'user' and group.voicemail_user_id:
            return self._cxml(self._user_voicemail_cxml(group.voicemail_user_id, number))
        if group.voicemail_mode == 'group':
            return self._cxml(self._group_voicemail_cxml(group, number))

        return self._dead_end_cxml(number)

    @http.route(
        '/signalwire/voice/ivr/<int:menu_id>/<int:phone_number_id>',
        type='http', auth='public', methods=['POST'], csrf=False)
    @signalwire_signed
    def ivr_menu(self, menu_id, phone_number_id, **kwargs):
        """Entry point for an IVR Menu - also re-entered for a
        "Go to Another Menu" option's own submenu, and for a re-prompt
        after an invalid digit (see ivr_digit below).
        """
        menu = request.env['signalwire.ivr.menu'].sudo().browse(menu_id)
        number = request.env['signalwire.phone_number'].sudo().browse(phone_number_id)
        if not menu.exists() or not number.exists():
            return self._dead_end_cxml(number)
        return self._cxml(self._ivr_menu_cxml(menu, number))

    @http.route(
        '/signalwire/voice/ivr/<int:menu_id>/<int:phone_number_id>/digit',
        type='http', auth='public', methods=['POST'], csrf=False)
    @signalwire_signed
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
            return self._dead_end_cxml(number)

        option = menu.option_ids.filtered(lambda o: o.digit == digit)[:1]
        if not option:
            # Same "exact literal, not translated" note as
            # _ivr_menu_cxml's own "no selection" message - kept in
            # sync with signalwire_voip_piper_tts's own
            # IVR_INVALID_OPTION_MESSAGE constant.
            invalid_option = self._say_or_play(
                'Sorry, that is not a valid option.', getattr(menu, 'piper_voice', False),
                getattr(menu, 'piper_speaker_id', False))
            return self._cxml(invalid_option + self._ivr_menu_cxml(menu, number))

        if option.action_type == 'hangup':
            self._mark_live_call_ended()
            return self._cxml('<Hangup/>')
        if option.action_type == 'submenu':
            if not option.target_submenu_id:
                return self._dead_end_cxml(number)
            return self._cxml(self._ivr_menu_cxml(option.target_submenu_id, number))
        if option.action_type == 'voicemail':
            if not option.target_user_id:
                return self._dead_end_cxml(number)
            return self._cxml(self._user_voicemail_cxml(option.target_user_id, number))
        if option.action_type == 'group':
            return self._ring_route_cxml('group', option.target_call_group_id, number)
        if option.action_type == 'callback_open':
            return self._callback_when_open_cxml(option, menu, number)

        # action_type == 'user'
        return self._ring_route_cxml('user', option.target_user_id, number)

    def _callback_when_open_cxml(self, option, menu, number):
        """Situation 3: after hours, "call me back when you open". Records a
        callback request for the option's call group that nobody is alerted
        to until the phones next open; then whoever is free is, in the
        order people called."""
        voice = (getattr(menu, 'piper_voice', False), getattr(menu, 'piper_speaker_id', False))
        if not self._caller_has_number():
            sorry = self._say_or_play(
                "Sorry, we can't call you back without your number.", *voice)
            return self._cxml(sorry + self._ivr_menu_cxml(menu, number))
        caller = request.httprequest.form.get('From', '')
        request.env['signalwire.callback_request'].sudo().create({
            'source': 'phone', 'phone_number': caller,
            'partner_id': request.env['res.users'].sudo()._signalwire_match_partner(
                caller).id or False,
            'target_group_id': option.target_call_group_id.id or False,
            'not_before': number._signalwire_next_opening(),
            'note': 'Asked after hours to be called back when we open.',
            'company_id': number.company_id.id or request.env.company.id,
        })
        self._mark_live_call_ended()
        thanks = self._say_or_play(
            'Thank you. We will call you back at the number you are calling from '
            'when we open. Goodbye.', *voice)
        return self._cxml(thanks + '<Hangup/>')

    @http.route(
        '/signalwire/voice/fallback/<int:user_id>/<int:phone_number_id>',
        type='http', auth='public', methods=['POST'], csrf=False)
    @signalwire_signed
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
            self._mark_live_call_ended()
            return self._cxml('')

        user = request.env['res.users'].sudo().browse(user_id)
        number = request.env['signalwire.phone_number'].sudo().browse(phone_number_id)
        if not user.exists() or not number.exists():
            return self._dead_end_cxml(number)
        return self._user_fallback_cxml(user, number, after=step)

    def _user_fallback_cxml(self, user, number, after=None):
        """What happens when `user` doesn't answer: their next configured
        step after `after` (forward, ring group, voicemail). Also where a
        call for someone who's Away starts, without ringing them first."""
        next_step = self._next_step(user, after=after)
        action = f'/signalwire/voice/fallback/{user.id}/{number.id}?step={next_step}'

        if next_step == 'forward':
            target = user.signalwire_active_forward_id.phone_number
            return self._cxml(
                f'<Dial timeout="{DIAL_TIMEOUT}" action="{action}">'
                f'<Number{self._answered_callback_attrs(user)}>{target}</Number></Dial>')

        if next_step == 'group':
            sip_domain = number.subproject_id.server_id._get_sip_domain()
            sips = ''.join(
                self._sip_targets(teammate, sip_domain)
                for teammate in user.signalwire_ring_group_ids)
            return self._cxml(
                f'<Dial timeout="{DIAL_TIMEOUT}" action="{action}">{sips}</Dial>')

        if next_step == 'voicemail':
            return self._cxml(self._user_voicemail_cxml(user, number))

        return self._dead_end_cxml(number)

    def _create_voicemail(self, number, from_number, duration, recording_url, transcribe, extra_vals):
        """Shared by a personal and a group voicemail box - fetches
        the recording into a real ir.attachment (SignalWire's own
        RecordingUrl needs our project credentials to fetch, same auth
        used everywhere else in this project), matches the caller
        against a contact, and creates+notifies the resulting
        signalwire.voicemail. `extra_vals` carries whichever of
        user_id/call_group_id actually owns this mailbox.
        """
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
                _logger.exception("SignalWire: could not fetch voicemail recording")

        partner = request.env['res.users'].sudo()._signalwire_match_partner(from_number)
        vals = {
            'phone_number_id': number.id,
            'from_number': from_number,
            'duration': duration,
            'recording_attachment_id': attachment.id or False,
            'recording_url': recording_url or False,
            'partner_id': partner.id if partner else False,
            'transcription_status': 'pending' if transcribe == '1' else 'none',
        }
        vals.update(extra_vals)
        voicemail = request.env['signalwire.voicemail'].sudo().create(vals)
        voicemail._log_and_notify()
        return voicemail

    @http.route(
        '/signalwire/voice/voicemail_complete/<int:user_id>/<int:phone_number_id>',
        type='http', auth='public', methods=['POST'], csrf=False)
    @signalwire_signed
    def voicemail_complete(self, user_id, phone_number_id, transcribe=None, **kwargs):
        form = request.httprequest.form
        user = request.env['res.users'].sudo().browse(user_id)
        number = request.env['signalwire.phone_number'].sudo().browse(phone_number_id)
        if not user.exists() or not number.exists():
            self._mark_live_call_ended()
            return self._cxml('<Hangup/>')

        self._create_voicemail(
            number, form.get('From', ''), int(form.get('RecordingDuration') or 0),
            form.get('RecordingUrl'), transcribe, {'user_id': user.id})
        self._mark_live_call_ended()
        return self._cxml('<Hangup/>')

    @http.route(
        '/signalwire/voice/group_voicemail_complete/<int:group_id>/<int:phone_number_id>',
        type='http', auth='public', methods=['POST'], csrf=False)
    @signalwire_signed
    def group_voicemail_complete(self, group_id, phone_number_id, **kwargs):
        form = request.httprequest.form
        group = request.env['signalwire.call.group'].sudo().browse(group_id)
        number = request.env['signalwire.phone_number'].sudo().browse(phone_number_id)
        if not group.exists() or not number.exists():
            self._mark_live_call_ended()
            return self._cxml('<Hangup/>')

        self._create_voicemail(
            number, form.get('From', ''), int(form.get('RecordingDuration') or 0),
            form.get('RecordingUrl'), None, {'call_group_id': group.id})
        self._mark_live_call_ended()
        return self._cxml('<Hangup/>')

    @http.route(
        '/signalwire/voice/greeting/<int:attachment_id>',
        type='http', auth='public', methods=['GET'])
    def voice_greeting(self, attachment_id, **kwargs):
        """Serves a user's or call group's own custom voicemail
        greeting recording to SignalWire's media server, which
        fetches <Play> URLs directly and unauthenticated - the normal
        backend playback route (/web/content/...) needs a logged-in
        session and won't work here. Scoped to attachments actually
        currently set as somebody's/some group's greeting (not an
        open-ended attachment-id fetch) - same accepted-risk shape as
        this module's own desk-phone auto-provisioning route: low-
        sensitivity content, publicly reachable by necessity, narrowly
        scoped rather than wide open.
        """
        attachment = request.env['ir.attachment'].sudo().search([
            ('id', '=', attachment_id), '|',
            '&', ('res_model', '=', 'res.users'),
            ('res_field', '=', 'signalwire_voicemail_greeting'),
            '&', ('res_model', '=', 'signalwire.call.group'),
            ('res_field', '=', 'voicemail_greeting'),
        ], limit=1)
        if not attachment:
            return request.not_found()
        stream = request.env['ir.binary']._get_stream_from(attachment, 'raw')
        return stream.get_response(as_attachment=False, max_age=None)

    @http.route(
        '/signalwire/voice/hold_music/<int:attachment_id>',
        type='http', auth='public', methods=['GET'])
    def hold_music(self, attachment_id, **kwargs):
        """Serves an uploaded hold-music file to SignalWire's media
        server, the same way voice_greeting serves a voicemail
        greeting recording - scoped to attachments currently set as
        some phone number's or call group's own hold_music, never an
        open-ended attachment-id fetch.
        """
        attachment = request.env['ir.attachment'].sudo().search([
            ('id', '=', attachment_id), '|',
            '&', ('res_model', '=', 'signalwire.phone_number'),
            ('res_field', '=', 'hold_music'),
            '&', ('res_model', '=', 'signalwire.call.group'),
            ('res_field', '=', 'hold_music'),
        ], limit=1)
        if not attachment:
            return request.not_found()
        stream = request.env['ir.binary']._get_stream_from(attachment, 'raw')
        return stream.get_response(as_attachment=False, max_age=None)

    @http.route(
        '/signalwire/voice/voicemail_transcription/<int:user_id>/<int:phone_number_id>',
        type='http', auth='public', methods=['POST'], csrf=False)
    @signalwire_signed
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

    def _queued_call(self, call_id):
        return request.env['signalwire.live_call'].sudo().browse(call_id).exists()

    @http.route(
        '/signalwire/voice/queue_wait/<int:call_id>', type='http', auth='public',
        methods=['POST'], csrf=False)
    @signalwire_signed
    def queue_wait(self, call_id, turn=None, **kwargs):
        """A waiting caller's hold loop. Each turn first checks whether
        someone has become free (in case nobody pushed the caller to them)."""
        call = self._queued_call(call_id)
        if not call or call.state == 'ended':
            return self._cxml('<Hangup/>')
        if call.state != 'queued':
            call._queue_join(group=call.queue_group_id, user=call.queue_user_id)
        agent = call._queue_try_offer()
        if agent:
            return self._cxml(self._queue_offer_dial_cxml(call, agent))
        return self._cxml(self._queue_wait_cxml(call, int(turn or 0)))

    @http.route(
        '/signalwire/voice/queue_choice/<int:call_id>', type='http', auth='public',
        methods=['POST'], csrf=False)
    @signalwire_signed
    def queue_choice(self, call_id, **kwargs):
        """A key pressed while waiting: 1 a callback, 2 a message,
        anything else back to waiting (keeping their place)."""
        call = self._queued_call(call_id)
        if not call or call.state == 'ended':
            return self._cxml('<Hangup/>')
        digit = request.httprequest.form.get('Digits', '')
        if digit == '1' and self._caller_has_number():
            caller = request.httprequest.form.get('From', '')
            request.env['signalwire.callback_request'].sudo().create({
                'source': 'phone', 'phone_number': caller,
                'partner_id': request.env['res.users'].sudo()._signalwire_match_partner(
                    caller).id or False,
                'target_user_id': call.queue_user_id.id or False,
                'target_group_id': (call.queue_group_id.id
                                    if not call.queue_user_id else False),
                'live_call_id': call.id,
                'company_id': call.company_id.id or request.env.company.id,
            })
            call.state = 'ended'
            return self._cxml(f'{self._say(self.CALLBACK_CONFIRM)}<Hangup/>')
        if digit == '2':
            kind, owner = self._queue_mailbox(call)
            if kind:
                # Out of the queue; the voicemail webhook finishes the record.
                call.write({'state': 'ended', 'offer_user_id': False})
                if kind == 'user':
                    return self._cxml(self._user_voicemail_cxml(owner, call.phone_number_id))
                return self._cxml(self._group_voicemail_cxml(owner, call.phone_number_id))
        return self._cxml(f'<Redirect>/signalwire/voice/queue_wait/{call.id}?turn=1</Redirect>')

    @http.route(
        '/signalwire/voice/queue_connect/<int:call_id>', type='http', auth='public',
        methods=['POST'], csrf=False)
    @signalwire_signed
    def queue_connect(self, call_id, **kwargs):
        """Where a waiting caller is redirected once an agent became free
        and was given them (signalwire.live_call._queue_push_to)."""
        call = self._queued_call(call_id)
        if not call or call.state == 'ended':
            return self._cxml('<Hangup/>')
        if call.state == 'ringing' and call.offer_user_id:
            return self._cxml(self._queue_offer_dial_cxml(call, call.offer_user_id))
        return self._cxml(self._queue_wait_cxml(call))

    @http.route(
        '/signalwire/voice/queue_result/<int:call_id>', type='http', auth='public',
        methods=['POST'], csrf=False)
    @signalwire_signed
    def queue_result(self, call_id, **kwargs):
        """The agent the caller was offered to answered (and the call is
        now over), or didn't: then the caller goes back in line in the same
        place and the next free agent is tried."""
        call = self._queued_call(call_id)
        if not call or call.state == 'ended':
            return self._cxml('<Hangup/>')
        if request.httprequest.form.get('DialCallStatus') == 'completed':
            call.state = 'ended'
            return self._cxml('')
        call._queue_offer_missed()
        agent = call._queue_try_offer()
        if agent:
            return self._cxml(self._queue_offer_dial_cxml(call, agent))
        return self._cxml(self._queue_wait_cxml(call, 1))

    @http.route(
        '/signalwire/voice/queue_timeout/<int:call_id>', type='http', auth='public',
        methods=['POST'], csrf=False)
    @signalwire_signed
    def queue_timeout(self, call_id, **kwargs):
        """The caller waited past the group's Longest Wait."""
        call = self._queued_call(call_id)
        if not call or call.state == 'ended':
            return self._cxml('<Hangup/>')
        call.write({'state': 'ended', 'offer_user_id': False})
        return self._group_unanswered_cxml(call.queue_group_id, call.phone_number_id)

    @http.route(
        '/signalwire/voice/screen/<int:user_id>', type='http', auth='public',
        methods=['POST'], csrf=False)
    @signalwire_signed
    def screen(self, user_id, caller=None, **kwargs):
        """Played to a Mobile user's phone when it answers, before the
        caller is connected: press 1 to take the call. Anything else
        (including the phone's own voicemail answering) hangs up this leg
        only; the caller keeps ringing the other phones."""
        who = ' '.join(re.sub(r'\D', '', caller or '')) or 'an unknown number'
        return self._cxml(
            f'<Gather numDigits="1" timeout="8" action="/signalwire/voice/screen_answer">'
            f'<Say>Call for you from {saxutils.escape(who)}. Press 1 to take it.</Say>'
            '</Gather><Hangup/>')

    @http.route(
        '/signalwire/voice/screen_answer', type='http', auth='public',
        methods=['POST'], csrf=False)
    @signalwire_signed
    def screen_answer(self, **kwargs):
        if request.httprequest.form.get('Digits') == '1':
            return self._cxml('')  # an empty response connects the caller
        return self._cxml('<Hangup/>')

    @http.route(
        '/signalwire/voice/status', type='http', auth='public',
        methods=['POST'], csrf=False)
    @signalwire_signed
    def call_status(self, **kwargs):
        """The number's own status callback (set by Connect Inbound
        Calls): SignalWire posts here when the caller's call is over,
        however it ended. Without it, a caller who hangs up while it's
        still ringing left the call "in progress" until the cleanup job."""
        status = request.httprequest.form.get('CallStatus', '')
        if status in FINISHED_STATUSES:
            self._mark_live_call_ended()
        return request.make_response('', status=204)

    @http.route(
        '/signalwire/voice/leg_answered/<int:user_id>', type='http', auth='public',
        methods=['POST'], csrf=False)
    @signalwire_signed
    def leg_answered(self, user_id, **kwargs):
        """One of the phones we rang picked up: the caller's call (the
        leg's parent) is now Connected, to this user."""
        form = request.httprequest.form
        parent_sid = form.get('ParentCallSid', '')
        if parent_sid and form.get('CallStatus') in ('in-progress', 'answered'):
            calls = request.env['signalwire.live_call'].sudo().search(
                [('call_sid', '=', parent_sid), ('state', '!=', 'ended')])
            user = request.env['res.users'].sudo().browse(user_id).exists()
            values = {'state': 'connected'}
            if user:
                values['assigned_user_id'] = user.id
            calls.write(values)
        return request.make_response('', status=204)

    @http.route(
        '/signalwire/voice/route_to_user/<int:user_id>/<int:phone_number_id>',
        type='http', auth='public', methods=['POST'], csrf=False)
    @signalwire_signed
    def route_to_user(self, user_id, phone_number_id, **kwargs):
        """A receptionist panel's own redirect target - see
        signalwire.live_call.action_route_to_user(). A plain one-shot
        dial with no further fallback chain of its own: once the
        panel has decided the destination, an unanswered call needs
        the receptionist to intervene again, the same way a real PBX
        attendant console works - it doesn't automatically keep
        hunting on its own.
        """
        user = request.env['res.users'].sudo().browse(user_id)
        number = request.env['signalwire.phone_number'].sudo().browse(phone_number_id)
        if not user.exists() or not number.exists():
            return self._dead_end_cxml(number)
        sip_domain = number.subproject_id.server_id._get_sip_domain()
        # The receptionist chose this person on purpose: ring them even if
        # they're Away (the panel shows it).
        dial = self._route_dial_cxml('user', user, number, sip_domain, ignore_presence=True)
        if not dial:
            return self._dead_end_cxml(number)
        return self._cxml(dial)

    @http.route(
        '/signalwire/voice/route_to_voicemail/<int:user_id>/<int:phone_number_id>',
        type='http', auth='public', methods=['POST'], csrf=False)
    @signalwire_signed
    def route_to_voicemail(self, user_id, phone_number_id, **kwargs):
        """A receptionist panel's own redirect target - see
        signalwire.live_call.action_send_to_voicemail().
        """
        user = request.env['res.users'].sudo().browse(user_id)
        number = request.env['signalwire.phone_number'].sudo().browse(phone_number_id)
        if not user.exists() or not number.exists():
            return self._dead_end_cxml(number)
        return self._cxml(self._user_voicemail_cxml(user, number))

    @http.route(
        '/signalwire/voice/hold_loop/<int:phone_number_id>',
        type='http', auth='public', methods=['POST'], csrf=False)
    @signalwire_signed
    def hold_loop(self, phone_number_id, user=None, **kwargs):
        """A receptionist panel's own redirect target while the
        receptionist places a separate, ordinary outbound call to
        check whether a colleague can take it - see
        signalwire.live_call.action_park() and this module's own
        README for why this deliberately isn't a 3-way conference
        bridge. Plays the message/music cycle (see _hold_cxml), then
        <Redirect>s back to this same URL - an indefinitely repeating
        cycle that stays audibly alive, rather than the single message
        followed by a long dead <Pause> this used to be.
        """
        number = request.env['signalwire.phone_number'].sudo().browse(phone_number_id)
        if not number.exists():
            return self._dead_end_cxml(number)
        target = request.env['res.users'].sudo().browse(int(user or 0)).exists()
        hold = self._hold_with_callback_offer(
            number, self.DEFAULT_HOLD_MESSAGE, 'signalwire.phone_number',
            'hold', target, number)
        again = f'/signalwire/voice/hold_loop/{phone_number_id}'
        if target:
            again += f'?user={target.id}'
        return self._cxml(f'{hold}<Redirect>{saxutils.escape(again)}</Redirect>')

    @http.route(
        '/signalwire/voice/callback_offer/<string:kind>/<int:target_id>/<int:phone_number_id>',
        type='http', auth='public', methods=['POST'], csrf=False)
    @signalwire_signed
    def callback_offer(self, kind, target_id, phone_number_id, attempt=None, **kwargs):
        """A key was pressed during hold. 1: record a callback request for
        whoever the caller was waiting for, thank them and hang up; they're
        alerted when free. Any other key: carry on where the hold was."""
        form = request.httprequest.form
        number = request.env['signalwire.phone_number'].sudo().browse(phone_number_id)
        if not number.exists() or kind not in ('group', 'hold'):
            self._mark_live_call_ended()
            return self._cxml('<Hangup/>')
        group = request.env['signalwire.call.group'].sudo().browse(
            target_id if kind == 'group' else 0).exists()
        user = request.env['res.users'].sudo().browse(
            target_id if kind == 'hold' else 0).exists()

        if form.get('Digits') == '1':
            caller = form.get('From', '')
            live_call = request.env['signalwire.live_call'].sudo().search(
                [('call_sid', '=', form.get('CallSid', ''))], limit=1)
            request.env['signalwire.callback_request'].sudo().create({
                'source': 'phone',
                'phone_number': caller,
                'partner_id': request.env['res.users'].sudo()._signalwire_match_partner(
                    caller).id or False,
                'target_user_id': user.id or False,
                'target_group_id': group.id or False,
                'live_call_id': live_call.id or False,
                'company_id': number.company_id.id or request.env.company.id,
            })
            self._mark_live_call_ended()
            return self._cxml(f'{self._say(self.CALLBACK_CONFIRM)}<Hangup/>')

        if kind == 'group' and group:
            return self._queue_join_cxml(number, group=group)
        again = f'/signalwire/voice/hold_loop/{number.id}'
        if user:
            again += f'?user={user.id}'
        return self._cxml(f'<Redirect>{saxutils.escape(again)}</Redirect>')

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
