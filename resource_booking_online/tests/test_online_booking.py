# -*- coding: utf-8 -*-
from freezegun import freeze_time

from odoo.exceptions import ValidationError
from odoo.tests.common import HttpCase, TransactionCase, tagged

from odoo.addons.resource_booking.tests.common import create_test_data


@tagged('post_install', '-at_install')
@freeze_time("2021-02-26 09:00:00", tick=True)
class TestVideoAppointments(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_test_data(cls)

    def _book(self, booking_type):
        return self.env['resource.booking'].create({
            'type_id': booking_type.id, 'partner_ids': [(6, 0, [self.partner.id])],
            'start': '2021-03-01 08:00:00'})

    def test_video_appointments_get_their_own_link(self):
        self.rbt.write({'video_appointment': True, 'videocall_location': False})
        booking = self._book(self.rbt)
        self.assertTrue(booking.meeting_id)
        self.assertIn('/calendar/join_videocall/', booking.meeting_id.videocall_location)

    def test_other_types_are_left_alone(self):
        booking = self._book(self.rbt)
        # The type's own location, untouched (Odoo makes it a full address).
        location = booking.meeting_id.videocall_location
        self.assertTrue(location.endswith('Videocall Main office'))
        self.assertNotIn('/calendar/join_videocall/', location)

    def test_online_types_need_an_organizer(self):
        with self.assertRaises(ValidationError):
            self.rbt.online_booking = True


@tagged('post_install', '-at_install')
class TestOnlineBookingPages(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_test_data(cls)
        cls.organizer = cls.users[0]
        cls.rbt.write({'online_booking': True, 'online_organizer_id': cls.organizer.id,
                       'online_description': 'A short consultation.'})
        cls.other = cls.rbt.copy({'name': 'Second type', 'online_booking': True,
                                  'online_organizer_id': cls.organizer.id})

    def _csrf(self, url):
        import re
        page = self.url_open(url).text
        return re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)

    def test_index_lists_the_bookable_types(self):
        page = self.url_open('/book').text
        self.assertIn('Test resource booking type', page)
        self.assertIn('Second type', page)

    def test_a_new_customer_books_then_picks_a_time(self):
        url = f'/book/{self.rbt.id}'
        response = self.url_open(url, data={
            'csrf_token': self._csrf(url), 'name': 'New Customer',
            'email': 'new.customer@example.com', 'phone': '707 555 0100'},
            allow_redirects=False)
        self.assertEqual(response.status_code, 303)
        booking = self.env['resource.booking'].search(
            [('partner_ids.email', '=', 'new.customer@example.com')])
        self.assertEqual(len(booking), 1)
        self.assertEqual(booking.user_id, self.organizer)
        self.assertIn(f'/my/bookings/{booking.id}/schedule?access_token={booking.access_token}',
                      response.headers['Location'])

    def test_an_existing_contact_is_reused(self):
        self.partner.email = 'known@example.com'
        url = f'/book/{self.rbt.id}'
        self.url_open(url, data={'csrf_token': self._csrf(url), 'name': 'Known',
                                 'email': 'Known@Example.com'}, allow_redirects=False)
        self.assertTrue(self.env['resource.booking'].search([('partner_ids', 'in', self.partner.ids)]))

    def test_bad_email_and_bots(self):
        url = f'/book/{self.rbt.id}'
        page = self.url_open(url, data={'csrf_token': self._csrf(url), 'name': 'X',
                                        'email': 'nope'}).text
        self.assertIn('valid email', page)
        bot = self.url_open(url, data={'csrf_token': self._csrf(url), 'name': 'Bot',
                                       'email': 'bot@example.com', 'website': 'spam'})
        self.assertEqual(bot.status_code, 404)
        self.assertFalse(self.env['res.partner'].search([('email', '=', 'bot@example.com')]))

    def test_types_not_online_are_not_found(self):
        self.other.online_booking = False
        self.assertEqual(self.url_open(f'/book/{self.other.id}').status_code, 404)
