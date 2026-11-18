# -*- coding: utf-8 -*-
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, tagged

NOTIFY = 'odoo.addons.calendar.models.calendar_attendee.CalendarAttendee._notify_attendees'


@tagged('post_install', '-at_install')
class TestPullQuietly(TransactionCase):
    """A pull must not email "Date updated" on every sync, nor take the
    calendar owner off their own event."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.owner = cls.env['res.users'].create({
            'name': 'Tiesa', 'login': 'tiesa@meskis.example', 'email': 'tiesa@meskis.example',
            'group_ids': [(4, cls.env.ref('base.group_user').id)]})
        # The same address on her companies' contacts too.
        cls.env['res.partner'].create({'name': 'DJ Em Bass', 'is_company': True, 'email': 'tiesa@meskis.example'})
        cls.env['res.partner'].create({'name': 'Meskis Works', 'is_company': True, 'email': 'TIESA@meskis.example'})
        cls.guest = cls.env['res.partner'].create({'name': 'Venue', 'email': 'venue@example.com'})
        cls.account = cls.env['caldav.account'].create({
            'user_id': cls.owner.id, 'name': 'My calendar', 'url': 'https://caldav.example/cal/'})
        cls.day = (fields.Datetime.now() + timedelta(days=20)).strftime('%Y%m%d')

    def _item(self, hour=15, attendees=('tiesa@meskis.example', 'venue@example.com'), etag='"1"'):
        lines = ''.join(f'ATTENDEE;PARTSTAT=ACCEPTED:mailto:{a}\r\n' for a in attendees)
        return {'href': 'https://caldav.example/cal/gig.ics', 'etag': etag, 'ics': (
            'BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nUID:gig@phone\r\nSUMMARY:DJ gig hold\r\n'
            f'DTSTART:{self.day}T{hour:02d}0000Z\r\nDTEND:{self.day}T{hour + 4:02d}0000Z\r\n'
            f'{lines}END:VEVENT\r\nEND:VCALENDAR\r\n')}

    def _event(self):
        return self.env['calendar.event'].search([('caldav_uid', '=', 'gig@phone')])

    def test_pulling_the_same_event_again_sends_nothing(self):
        with patch(NOTIFY) as notify:
            self.account._caldav_apply_remote_event(self._item())
            for n in range(3):  # three more syncs, nothing changed
                self.account._caldav_apply_remote_event(self._item(etag=f'"{n + 2}"'))
        self.assertFalse(notify.called)
        self.assertEqual(len(self._event()), 1)

    def test_a_date_moved_on_the_phone_moves_quietly(self):
        self.account._caldav_apply_remote_event(self._item())
        with patch(NOTIFY) as notify:
            self.account._caldav_apply_remote_event(self._item(hour=17, etag='"2"'))
        self.assertFalse(notify.called)
        self.assertEqual(self._event().start.hour, 17)

    def test_the_owner_stays_on_their_own_event(self):
        self.account._caldav_apply_remote_event(self._item())
        event = self._event()
        self.assertIn(self.owner.partner_id, event.partner_ids)
        self.assertIn(self.guest, event.partner_ids)
        self.assertEqual(len(event.partner_ids), 2)  # not her company contacts
        # An event made on the phone with no attendees is still hers.
        self.account._caldav_apply_remote_event(self._item(attendees=(), etag='"2"'))
        self.assertEqual(self._event().partner_ids, self.owner.partner_id)
