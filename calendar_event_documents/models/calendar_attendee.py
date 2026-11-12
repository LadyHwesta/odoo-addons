# -*- coding: utf-8 -*-
from odoo import models

# The emails that carry the meeting's documents. Reminders and cancellations
# don't.
DOCUMENT_TEMPLATES = (
    'calendar.calendar_template_meeting_invitation',
    'calendar.calendar_template_meeting_update',
    'calendar.calendar_template_meeting_changedate',
)


class CalendarAttendee(models.Model):
    _inherit = 'calendar.attendee'

    def _notify_attendees(self, mail_template, notify_author=False, force_send=False):
        templates = [self.env.ref(x, raise_if_not_found=False) for x in DOCUMENT_TEMPLATES]
        if mail_template and mail_template in templates:
            self = self.with_context(calendar_documents_in_mail=True)
        return super()._notify_attendees(
            mail_template, notify_author=notify_author, force_send=force_send)
