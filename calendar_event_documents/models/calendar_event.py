# -*- coding: utf-8 -*-
import logging

from markupsafe import Markup

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

# Above this, the documents aren't attached to invitation emails (most mail
# servers refuse messages near 25 MB); the email says so instead.
MAX_MAIL_DOCUMENTS_BYTES = 15 * 1024 * 1024


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    document_ids = fields.Many2many(
        'ir.attachment', 'calendar_event_document_rel', 'event_id', 'attachment_id',
        string="Documents", copy=False,
        help="Agenda, minutes, papers: files for this meeting. They show for "
             "everyone who can open the meeting.")
    document_count = fields.Integer(compute='_compute_document_count')
    videocall_documents_message_id = fields.Many2one(
        'mail.message', copy=False, readonly=True,
        help="The pinned message listing this meeting's documents in its video "
             "call's chat.")
    documents_in_invitations = fields.Boolean(
        string="Send Documents with Invitations", default=True,
        help="Attach the meeting's documents to invitation, update and "
             "date-change emails sent to attendees.")

    @api.depends('document_ids')
    def _compute_document_count(self):
        for event in self:
            event.document_count = len(event.document_ids)

    def _claim_documents(self):
        """Files added before the meeting was first saved have no record to
        belong to yet: make them this meeting's, so its access applies."""
        for event in self:
            event.document_ids.filtered(lambda a: not a.res_id).sudo().write(
                {'res_model': self._name, 'res_id': event.id})

    @api.model_create_multi
    def create(self, vals_list):
        events = super().create(vals_list)
        events._claim_documents()
        return events

    def write(self, vals):
        result = super().write(vals)
        if 'document_ids' in vals:
            self._claim_documents()
            self.filtered('videocall_channel_id')._post_call_documents()
        return result

    def _message_post_after_hook(self, message, msg_vals):
        # Files sent with a chatter message, or by replying to the invitation,
        # are the meeting's documents too.
        if message.attachment_ids:
            self.sudo().document_ids = [(4, a.id) for a in message.attachment_ids]
        return super()._message_post_after_hook(message, msg_vals)

    # -- The meeting's video call ---------------------------------------------

    def _create_videocall_channel(self):
        result = super()._create_videocall_channel()
        self._post_call_documents()
        return result

    def _documents_for_call(self):
        """The files listed in the meeting's video call chat."""
        self.ensure_one()
        return self._shared_documents()

    def _call_documents_body(self, documents):
        """Download links anyone in the call can open, guests from the
        invitation link included: each carries the file's own access token."""
        base = self.get_base_url()
        items = Markup('').join(
            Markup('<li><a href="%s" target="_blank">%s</a></li>') % (
                f"{base}/web/content/{doc.id}?access_token={doc.sudo().generate_access_token()[0]}"
                f"&download=true", doc.name)
            for doc in documents)
        return Markup('<p><b>%s</b></p><ul>%s</ul>') % (
            _("Meeting documents for %(meeting)s", meeting=self.name), items)

    def _post_call_documents(self):
        """Lists the documents in the meeting's video call chat, as one
        pinned message kept up to date, so everyone in the call can open
        them on their own device."""
        for event in self.filtered('videocall_channel_id'):
            documents = event.sudo()._documents_for_call()
            channel = event.videocall_channel_id.sudo()
            message = event.videocall_documents_message_id.sudo()
            if message.exists() and message.model == 'discuss.channel' and message.res_id == channel.id:
                body = event._call_documents_body(documents) if documents else \
                    Markup('<p>%s</p>') % _("No documents for this meeting.")
                channel._message_update_content(message, body=body)
                continue
            if not documents:
                continue
            author = event.user_id.partner_id or self.env.ref('base.partner_root')
            message = channel.message_post(
                body=event._call_documents_body(documents), author_id=author.id,
                message_type='comment', subtype_xmlid='mail.mt_comment')
            message.pinned_at = fields.Datetime.now()
            event.sudo().videocall_documents_message_id = message

    def _documents_for_mail(self):
        """Every file on this meeting, private or not; add-ons add theirs."""
        self.ensure_one()
        return self.document_ids

    def _shared_documents(self):
        """The files attendees get: emailed with invitations and listed in the
        video call. Private ones stay on the meeting for the team only."""
        return self._documents_for_mail().filtered(lambda d: not d.meeting_private)

    def message_notify(self, **kwargs):
        # Only for the invitation, update and date-change emails (see
        # calendar.attendee._notify_attendees), and only one meeting at a time.
        if not self.env.context.get('calendar_documents_in_mail') or len(self) != 1 \
                or not self.documents_in_invitations:
            return super().message_notify(**kwargs)
        documents = self.sudo()._shared_documents()
        if not documents:
            return super().message_notify(**kwargs)
        if sum(documents.mapped('file_size')) > MAX_MAIL_DOCUMENTS_BYTES:
            _logger.info("Meeting %s: documents too large to email, listed instead.", self.id)
            note = _("This meeting has documents that are too large to email: "
                     "open the meeting in Odoo to see them.")
            # The body is the rendered invitation template: already HTML.
            kwargs['body'] = Markup(kwargs.get('body') or '') + Markup('<p>%s</p>') % note
            return super().message_notify(**kwargs)
        copies = self.env['ir.attachment'].sudo().create([
            doc.copy_data({'res_model': 'mail.compose.message', 'res_id': 0})[0]
            for doc in documents])
        kwargs['attachment_ids'] = list(kwargs.get('attachment_ids') or []) + copies.ids
        return super().message_notify(**kwargs)


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    meeting_private = fields.Boolean(
        string="Private",
        help="Kept on the meeting for your team only: not sent with invitations "
             "and not listed in the meeting's video call.")

    def write(self, vals):
        result = super().write(vals)
        if 'meeting_private' in vals:
            if vals['meeting_private']:
                # Cancels any download link already shared in a call.
                self.sudo().access_token = False
            self._meetings_using().filtered('videocall_channel_id')._post_call_documents()
        return result

    def _meetings_using(self):
        """Meetings these files belong to; add-ons add their own links."""
        return self.env['calendar.event'].sudo().search([('document_ids', 'in', self.ids)])

    def _post_add_create(self, **kwargs):
        # A file attached with the chatter's paperclip on a meeting becomes
        # one of its documents, so it shows on the Documents tab.
        result = super()._post_add_create(**kwargs)
        for attachment in self.filtered(
                lambda a: a.res_model == 'calendar.event' and a.res_id and not a.res_field):
            event = self.env['calendar.event'].sudo().browse(attachment.res_id).exists()
            if event:
                event.document_ids = [(4, attachment.id)]
        return result

    def action_calendar_download(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self.id}?download=true',
            'target': 'self',
        }
