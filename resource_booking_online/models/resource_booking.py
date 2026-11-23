# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResourceBookingType(models.Model):
    _inherit = 'resource.booking.type'

    online_booking = fields.Boolean(
        string="Bookable Online",
        help="List this type on the public Book an Appointment page (/book), where "
             "anyone can book it with their name and email.")
    online_organizer_id = fields.Many2one(
        'res.users', string="Organizer",
        help="Online bookings go on this person's calendar, in their name, and use "
             "their video tier.")
    video_appointment = fields.Boolean(
        help="Each booked appointment gets its own video link, sent in its invitation.")
    online_description = fields.Text(
        string="Online Description",
        help="A line or two shown under this type on the Book an Appointment page.")

    @api.constrains('online_booking', 'online_organizer_id')
    def _check_online_organizer(self):
        for booking_type in self.filtered('online_booking'):
            if not booking_type.online_organizer_id:
                raise ValidationError(self.env._(
                    "Choose an Organizer for %(type)s before it can be booked online.",
                    type=booking_type.name))


class ResourceBooking(models.Model):
    _inherit = 'resource.booking'

    def _sync_meeting(self):
        result = super()._sync_meeting()
        for booking in self.filtered(
                lambda b: b.type_id.video_appointment and b.meeting_id
                and not b.meeting_id.videocall_location):
            # The meeting's own video link (or Premium video, when the
            # organizer has it: telehealth_booking overrides this).
            booking.meeting_id.sudo()._set_discuss_videocall_location()
        return result
