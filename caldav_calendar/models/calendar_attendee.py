# -*- coding: utf-8 -*-
from odoo import models


class CalendarAttendee(models.Model):
    _inherit = 'calendar.attendee'

    def _send_invitation_emails(self):
        # An event coming in from CalDAV was already sent to whoever it
        # concerns by the calendar it was made in.
        if self.env.context.get('caldav_no_sync'):
            return
        return super()._send_invitation_emails()
