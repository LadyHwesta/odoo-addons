# -*- coding: utf-8 -*-
from odoo import fields, models


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    dms_file_ids = fields.Many2many(
        'dms.file', 'calendar_event_dms_file_rel', 'event_id', 'file_id',
        string="Linked Files", copy=False,
        help="Files kept in Documents (for example a team folder), linked "
             "rather than copied, so everyone works on the same file. "
             "People who can't open that folder won't be able to open "
             "them from the meeting either.")

    def _documents_for_mail(self):
        # Linked files go out with invitations too, when they're kept as
        # attachments (Attachment storage, as team folders are).
        return super()._documents_for_mail() | self.dms_file_ids.attachment_id


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    def _meetings_using(self):
        return super()._meetings_using() | self.env['calendar.event'].sudo().search(
            [('dms_file_ids.attachment_id', 'in', self.ids)])


class DmsFile(models.Model):
    _inherit = 'dms.file'

    meeting_private = fields.Boolean(
        related='attachment_id.meeting_private', readonly=False, string="Private",
        help="Not sent with invitations and not listed in a meeting's video call.")
