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
