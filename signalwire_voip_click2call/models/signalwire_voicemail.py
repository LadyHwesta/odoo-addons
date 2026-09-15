# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import _, api, fields, models


class SignalWireVoicemail(models.Model):
    """A voicemail left when a call fell all the way through the
    fallback chain (softphone -> forward -> ring group, whichever of
    those are configured) with nobody picking up. Its own mail.thread
    carries the recording + an activity for the intended agent
    regardless of whether the caller could be matched to a contact;
    if they can be, the same message also gets cross-posted to that
    contact's own chatter, same convention as signalwire_sms's own
    message logging.

    Self-service "full control" for the owning user: an ir.rule (see
    security/signalwire_voicemail_security.xml) scopes a plain
    internal user to their own records with real read/write/unlink,
    so they can mark read/unread, listen, and delete without any
    admin involvement - only signalwire.voicemail.system (managers)
    can see everyone's.
    """
    _name = 'signalwire.voicemail'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'SignalWire Voicemail'
    _order = 'create_date desc'
    _rec_name = 'from_number'

    phone_number_id = fields.Many2one('signalwire.phone_number', required=True, ondelete='cascade')
    user_id = fields.Many2one(
        'res.users', required=True, ondelete='cascade',
        help="Who this voicemail was left for.")
    from_number = fields.Char(required=True)
    duration = fields.Integer(help="Seconds.")
    recording_attachment_id = fields.Many2one('ir.attachment', readonly=True)
    recording_download_url = fields.Char(
        compute='_compute_recording_download_url',
        help="Plain relative URL for inline playback in the backend - "
             "kept as a separate computed field rather than making JS "
             "resolve the ir.attachment relation itself.")
    recording_url = fields.Char(
        readonly=True,
        help="SignalWire's own RecordingUrl for this voicemail (without "
             "the .mp3 suffix we append to fetch it) - kept around "
             "purely to correlate the async transcription webhook back "
             "to this record later, since that webhook doesn't carry "
             "our own user_id/phone_number_id in its path the way the "
             "recording-complete one does.")
    partner_id = fields.Many2one(
        'res.partner',
        help="Best-effort match against the caller's number - same "
             "digits-only approach as signalwire_sms's own chatter "
             "matching, duplicated here rather than shared since "
             "this module doesn't depend on signalwire_sms.")
    is_read = fields.Boolean(default=False)
    transcription_status = fields.Selection(
        [('none', 'Not Requested'), ('pending', 'Pending'),
         ('completed', 'Completed'), ('failed', 'Failed')],
        default='none', required=True,
        help="'Pending' means the recording was sent to SignalWire for "
             "transcription and we're waiting on its transcribeCallback "
             "webhook - sourced from SignalWire's own docs (transcribe/"
             "transcribeCallback on the <Record> verb), not yet live-"
             "verified end to end against a real spoken voicemail.")
    transcription_text = fields.Text(readonly=True)

    def _compute_recording_download_url(self):
        for voicemail in self:
            voicemail.recording_download_url = (
                f'/web/content/{voicemail.recording_attachment_id.id}?download=false'
                if voicemail.recording_attachment_id else False)

    def _notify_systray(self):
        """Ping each affected user's own bus channel so the voicemail
        systray (see this module's static/src/) refreshes instantly
        instead of on its own next poll - same "user._bus_send via
        res.users' own _bus_channel -> partner" mechanism core's own
        mail.activity systray badge already relies on.
        """
        for user in self.mapped('user_id'):
            user._bus_send('signalwire_voicemail/updated', {})

    def action_mark_read(self):
        self.write({'is_read': True})
        self._notify_systray()

    def action_mark_unread(self):
        self.write({'is_read': False})
        self._notify_systray()

    @api.model
    def get_systray_data(self):
        """Everything the voicemail systray dropdown needs for the
        current user in one round trip: the unread count (for the
        badge) and a short preview list (caller, duration, transcript
        snippet if one's ready, a playable recording URL) - enough for
        someone to decide whether to open the full record at all.
        """
        unread = self.search([('user_id', '=', self.env.uid), ('is_read', '=', False)])
        preview = unread[:5]
        return {
            'count': len(unread),
            'voicemails': [{
                'id': voicemail.id,
                'from_number': voicemail.from_number,
                'partner_name': voicemail.partner_id.name or False,
                'duration': voicemail.duration,
                'transcription_status': voicemail.transcription_status,
                'transcription_text': voicemail.transcription_text,
                'recording_download_url': voicemail.recording_download_url,
            } for voicemail in preview],
        }

    def _log_and_notify(self):
        """Cross-post to the matched contact's chatter (if any) and
        schedule a "return this call" activity for the intended agent
        either way - the guaranteed notification, since a caller not
        matching any contact shouldn't mean the voicemail goes
        unnoticed.
        """
        for voicemail in self:
            attachments = voicemail.recording_attachment_id.ids
            body = _(
                "Voicemail from %(number)s (%(duration)ss)",
                number=voicemail.from_number, duration=voicemail.duration)
            voicemail.message_post(body=body, attachment_ids=attachments)
            if voicemail.partner_id:
                voicemail.partner_id.message_post(body=body, attachment_ids=attachments)
            voicemail.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=voicemail.user_id.id,
                summary=_("Return voicemail from %(number)s", number=voicemail.from_number),
                note=body)
        self._notify_systray()

    def _log_transcription(self, status, text):
        """Called by the transcribeCallback webhook once SignalWire
        finishes (or fails) transcribing the recording - posts the
        transcript to chatter (same places the original voicemail
        notice went) and folds it into the still-open "return this
        call" activity's own note, so a user scanning the Activities
        systray sees the transcript without opening anything.
        """
        self.ensure_one()
        self.write({
            'transcription_status': status,
            'transcription_text': text or False,
        })
        if status == 'completed' and text:
            # `text` is free-form speech-to-text output, not trusted
            # input - built via Markup's own % so it (and the
            # translated label) get HTML-escaped, not concatenated in
            # raw and posted straight into an Html field.
            body = Markup("%s %s") % (_("Transcript:"), text)
            self.message_post(body=body)
            if self.partner_id:
                self.partner_id.message_post(body=body)
            if self.activity_ids:
                addition = Markup("<br/>%s") % body
                self.activity_ids.write({'note': (self.activity_ids[0].note or '') + addition})
        self._notify_systray()
