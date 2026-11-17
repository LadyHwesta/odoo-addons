# -*- coding: utf-8 -*-
from datetime import date, datetime, timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestGigBooking(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.write({'gig_tz': 'America/Los_Angeles', 'gig_buffer_hours': 2,
                               'gig_balance_days': 14})
        cls.client = cls.env['res.partner'].create({'name': 'Maya & Jordan', 'email': 'maya@example.com'})
        cls.product = cls.env['product.product'].create({
            'name': 'DJ package, 4 hours', 'type': 'service', 'list_price': 800})

    def _order(self, day, start=19.0, end=23.0, confirm=False):
        order = self.env['sale.order'].create({
            'partner_id': self.client.id, 'gig_date': day, 'gig_start_hour': start,
            'gig_end_hour': end, 'venue_name': 'Ledson Winery',
            'order_line': [(0, 0, {'product_id': self.product.id})]})
        if confirm:
            order.with_context(gig_conflict_ok=True).action_confirm()
        return order

    # ---- times ----

    def test_times_are_in_the_gig_time_zone(self):
        order = self._order(date(2026, 12, 5), 19.5, 23.0)
        self.assertEqual(order.gig_start, datetime(2026, 12, 6, 3, 30))  # 19:30 PST = 03:30 UTC
        self.assertEqual(order.gig_end, datetime(2026, 12, 6, 7, 0))

    def test_an_end_before_the_start_runs_past_midnight(self):
        order = self._order(date(2026, 12, 5), 21.0, 2.0)
        self.assertEqual(order.gig_end - order.gig_start, timedelta(hours=5))

    # ---- double booking ----

    def test_overlapping_gigs_are_flagged_and_confirming_is_stopped(self):
        self._order(date(2026, 12, 5), 19.0, 23.0, confirm=True)
        clash = self._order(date(2026, 12, 6), 0.5, 3.0)  # 30 min after the other ends: inside the 2 h gap
        self.assertTrue(clash.gig_has_conflict)
        self.assertIn('Maya & Jordan', clash.gig_conflict_summary)
        # A person (not the system) confirming: tests run as the system by default.
        as_person = clash.with_user(self.env.ref('base.user_admin'))
        with self.assertRaisesRegex(UserError, 'clashes with'):
            as_person.action_confirm()
        as_person.action_confirm_gig_anyway()
        self.assertEqual(clash.state, 'sale')

    def test_far_enough_apart_is_fine(self):
        self._order(date(2026, 12, 5), 19.0, 23.0, confirm=True)
        self.assertFalse(self._order(date(2026, 12, 7)).gig_has_conflict)

    def test_events_and_appearances_count_too(self):
        self.env['event.event'].create({
            'name': 'Club Night', 'is_appearance': True, 'appearance_entry': 'free',
            'date_begin': datetime(2026, 12, 13, 5, 0), 'date_end': datetime(2026, 12, 13, 9, 0)})
        order = self._order(date(2026, 12, 12), 20.0, 23.0)  # 04:00-07:00 UTC
        self.assertTrue(order.gig_has_conflict)
        self.assertIn('Club Night', order.gig_conflict_summary)

    def test_a_paid_deposit_still_books_it_with_a_warning(self):
        self._order(date(2026, 12, 5), 19.0, 23.0, confirm=True)
        clash = self._order(date(2026, 12, 5), 20.0, 22.0)
        clash.sudo().action_confirm()  # the payment flow confirms as the system
        self.assertEqual(clash.state, 'sale')
        self.assertTrue(clash.activity_ids.filtered(lambda a: a.summary == 'Double booking'))

    # ---- lead to quote ----

    def test_quote_from_a_lead_starts_with_its_gig_details(self):
        lead = self.env['crm.lead'].create({
            'name': 'Booking request', 'gig_date': date(2026, 12, 19), 'gig_type': 'wedding',
            'gig_start_hour': 17.0, 'gig_end_hour': 22.0, 'venue_name': 'Ledson Winery',
            'contact_name': 'Maya', 'type': 'opportunity', 'partner_id': self.client.id})
        self.assertEqual(lead.name, 'Booking request: Wedding 2026-12-19 Maya')
        context = lead._prepare_opportunity_quotation_context()
        order = self.env['sale.order'].with_context(context).create({'partner_id': self.client.id})
        self.assertEqual((order.gig_date, order.gig_type, order.venue_name),
                         (date(2026, 12, 19), 'wedding', 'Ledson Winery'))

    def test_request_form_creates_a_lead_with_the_gig(self):
        response = self.url_open('/website/form/crm.lead', data={
            'name': 'Booking request', 'contact_name': 'Sam', 'email_from': 'sam@example.com',
            'gig_type': 'private', 'gig_date': '2026-12-20', 'gig_start_hour': '19.5',
            'gig_end_hour': '23.0', 'venue_name': 'Backyard', 'guest_count': '60',
            'description': 'Birthday'})
        self.assertEqual(response.status_code, 200)
        lead = self.env['crm.lead'].search([('email_from', '=', 'sam@example.com')])
        self.assertEqual((lead.gig_date, lead.gig_start_hour, lead.guest_count),
                         (date(2026, 12, 20), 19.5, 60))
        self.assertTrue(lead.name.startswith('Booking request: Private party'))

    def test_book_page_renders(self):
        body = self.url_open('/book').text
        self.assertIn('gig_booking_form', body)
        self.assertIn('7:30 pm', body)

    # ---- after booking ----

    def test_promote_creates_a_draft_appearance(self):
        order = self._order(date(2026, 12, 5), confirm=True)
        order.action_promote_gig()
        event = order.gig_event_id
        self.assertTrue(event.is_appearance)
        self.assertFalse(event.website_published)
        self.assertEqual((event.date_begin, event.date_end), (order.gig_start, order.gig_end))
        self.assertFalse(order.gig_has_conflict)  # its own appearance isn't a clash

    def test_balance_to_do_once_within_the_window(self):
        soon = fields.Date.context_today(self.env['sale.order']) + timedelta(days=10)
        order = self._order(soon, confirm=True)
        self.env['sale.order']._cron_gig_balance_reminders()
        self.env['sale.order']._cron_gig_balance_reminders()
        self.assertEqual(len(order.activity_ids.filtered(lambda a: a.summary == 'Invoice the balance')), 1)

    def test_booked_dates_calendar_lists_gigs_and_events(self):
        order = self._order(date(2026, 12, 5), confirm=True)
        self.env['event.event'].create({
            'name': 'Our Party', 'date_begin': datetime(2027, 1, 1, 3, 0),
            'date_end': datetime(2027, 1, 1, 8, 0)})
        self.env.flush_all()
        slots = self.env['gig.booking.slot'].search([])
        self.assertIn(order, slots.order_id)
        self.assertIn('Our Party', slots.mapped('name'))
