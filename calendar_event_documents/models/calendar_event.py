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
        return result

    def _documents_for_mail(self):
        """The files sent with this meeting's emails; add-ons add theirs."""
        self.ensure_one()
        return self.document_ids

    def message_notify(self, **kwargs):
        # Only for the invitation, update and date-change emails (see
        # calendar.attendee._notify_attendees), and only one meeting at a time.
        if not self.env.context.get('calendar_documents_in_mail') or len(self) != 1 \
                or not self.documents_in_invitations:
            return super().message_notify(**kwargs)
        documents = self.sudo()._documents_for_mail()
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

    def action_calendar_download(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self.id}?download=true',
            'target': 'self',
        }
