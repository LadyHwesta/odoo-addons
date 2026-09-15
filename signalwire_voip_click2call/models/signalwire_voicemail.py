# -*- coding: utf-8 -*-
from odoo import _, fields, models


class SignalWireVoicemail(models.Model):
    """A voicemail left when a call fell all the way through the
    fallback chain (softphone -> forward -> ring group, whichever of
    those are configured) with nobody picking up. Its own mail.thread
    carries the recording + an activity for the intended agent
    regardless of whether the caller could be matched to a contact;
    if they can be, the same message also gets cross-posted to that
    contact's own chatter, same convention as signalwire_sms's own
    message logging.
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
    partner_id = fields.Many2one(
        'res.partner',
        help="Best-effort match against the caller's number - same "
             "digits-only approach as signalwire_sms's own chatter "
             "matching, duplicated here rather than shared since "
             "this module doesn't depend on signalwire_sms.")

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
