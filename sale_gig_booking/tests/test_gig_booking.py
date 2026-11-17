# -*- coding: utf-8 -*-
import re
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

    def test_requests_go_to_a_team_in_the_websites_own_company(self):
        """djembass.com belongs to another company than the default lead
        team: the request must not fail."""
        other = self.env['res.company'].create({'name': 'DJ Company'})
        own_team = self.env['crm.team'].create({'name': 'DJ Team', 'company_id': other.id})
        website = self.env['website'].get_current_website()
        website.write({'company_id': other.id})
        if 'salesteam_id' in website._fields:
            website.salesteam_id = own_team
        else:
            website.crm_default_team_id = own_team
        self.assertIn(f'name="team_id" value="{own_team.id}"', self.url_open('/book').text)


    # ---- load-in sheet ----

    def test_load_in_sheet_prints_the_day(self):
        order = self._order(date(2026, 12, 5), 19.5, 1.0)
        order.write({'gig_load_in_hour': 17.25, 'gig_contact_name': 'Pat (venue)',
                     'gig_contact_phone': '+1 707 555 0100', 'gig_load_in_notes': 'Back door, 2 steps'})
        self.assertEqual(order._gig_sheet_times(), {'load_in': '17:15', 'start': '19:30', 'end': '01:00'})
        html = self.env['ir.actions.report']._render_qweb_html(
            'sale_gig_booking.report_gig_load_in', order.ids)[0].decode()
        for text in ('Ledson Winery', '17:15', 'Pat (venue)', 'Back door, 2 steps', 'DJ package, 4 hours'):
            self.assertIn(text, html)

    # ---- timeline ----

    def test_timeline_runs_past_midnight_in_order(self):
        order = self._order(date(2026, 12, 31), 20.0, 1.0)
        Line = self.env['gig.timeline.line']
        for hour, moment in ((0.0, 'Countdown'), (20.5, 'Doors'), (0.75, 'Last song'), (21.0, 'First set')):
            Line.create({'order_id': order.id, 'hour': hour, 'moment': moment})
        order.invalidate_recordset(['gig_timeline_ids'])  # read back in the stored order
        self.assertEqual(order.gig_timeline_ids.mapped('moment'), ['Doors', 'First set', 'Countdown', 'Last song'])
        self.assertEqual(order.gig_timeline_ids[2]._hhmm(), '00:00')

    def _csrf(self, html):
        found = re.search(r'name="csrf_token" value="([^"]+)"', html) or re.search(
            r'name="csrf_token" value="([^"]+)"', self.url_open('/web/login').text)
        return found.group(1)

    def _client_post(self, order, **data):
        html = self.url_open(order.get_portal_url(suffix='/timeline')).text
        data.update(csrf_token=self._csrf(html), access_token=order._portal_ensure_token())
        return self.url_open(f'/my/orders/{order.id}/timeline', data=data)

    def test_client_plans_their_timeline_in_the_portal(self):
        order = self._order(fields.Date.today() + timedelta(days=30), 17.0, 23.0)
        order._portal_ensure_token()
        self.assertIn('Your event timeline', self.url_open(order.get_portal_url()).text)
        self._client_post(order, time='18:15', moment='First dance', note='At Last')
        self._client_post(order, time='18:00', moment=' Grand  entrance ')
        self._client_post(order, time='25:00', moment='Nonsense')
        self.assertEqual(order.gig_timeline_ids.mapped('moment'), ['Grand entrance', 'First dance'])
        self.assertTrue(all(order.gig_timeline_ids.mapped('added_by_client')))
        self.assertIn('First dance', self.url_open(order.get_portal_url(suffix='/timeline')).text)
        other = self._order(fields.Date.today() + timedelta(days=60))
        theirs = self.env['gig.timeline.line'].create({'order_id': other.id, 'hour': 19, 'moment': 'X'})
        self._client_post(order, remove=str(theirs.id))
        self.assertTrue(theirs.exists())
        self._client_post(order, remove=str(order.gig_timeline_ids[0].id))
        self.assertEqual(order.gig_timeline_ids.mapped('moment'), ['First dance'])

    def test_timeline_locks_when_the_gig_starts(self):
        order = self._order(fields.Date.today() - timedelta(days=1))
        self.assertIn('locked', self._client_post(order, time='18:00', moment='Late').text)
        self.assertFalse(order.gig_timeline_ids)

    def test_gig_sheet_has_the_booking_and_timeline(self):
        order = self._order(date(2026, 12, 5), 19.0, 0.0)
        self.env['gig.timeline.line'].create({'order_id': order.id, 'hour': 19.5, 'moment': 'Grand entrance'})
        html = self.env['ir.actions.report']._render_qweb_html(
            'sale_gig_booking.report_gig_load_in', order.ids)[0].decode()
        for text in ('Timeline', '19:30', 'Grand entrance', order.name, 'maya@example.com', '00:00'):
            self.assertIn(text, html)

    # ---- billing the gig's hours ----

    def test_hourly_products_bill_the_gigs_length(self):
        hourly = self.env['product.product'].create({
            'name': 'DJ, per hour', 'type': 'service', 'list_price': 150, 'gig_bill_hours': True})
        order = self._order(date(2026, 12, 5), 19.0, 23.5)
        line = self.env['sale.order.line'].create({'order_id': order.id, 'product_id': hourly.id})
        flat = order.order_line - line
        self.assertEqual(line.product_uom_qty, 4.5)
        self.assertEqual(flat.product_uom_qty, 1)  # other products keep their quantity
        order.gig_end_hour = 1.0  # runs past midnight now
        self.assertEqual(line.product_uom_qty, 6)
        self.env.company.gig_min_hours = 8
        order.gig_end_hour = 22.0
        self.assertEqual(line.product_uom_qty, 8)
        order.with_context(gig_conflict_ok=True).action_confirm()
        order.gig_end_hour = 23.0
        self.assertEqual(line.product_uom_qty, 8, "a booked gig's hours stay as agreed")

    def test_quote_templates_use_the_gigs_hours(self):
        hourly = self.env['product.product'].create({
            'name': 'Sound engineer, per hour', 'type': 'service', 'list_price': 125, 'gig_bill_hours': True})
        template = self.env['sale.order.template'].create({
            'name': 'Sound', 'sale_order_template_line_ids': [(0, 0, {'product_id': hourly.id, 'product_uom_qty': 1})]})
        order = self._order(date(2026, 12, 5), 18.0, 22.0)
        order.sale_order_template_id = template
        order._onchange_sale_order_template_id()
        line = order.order_line.filtered(lambda l: l.product_id == hourly)
        self.assertEqual(line.product_uom_qty, 4)

    def test_booking_creates_the_products_todo(self):
        research = self.env['product.product'].create({
            'name': 'Sound engineer, house gear', 'type': 'service', 'list_price': 125,
            'gig_booked_todo': "Get the venue's equipment list\nResearch each piece before the gig."})
        order = self._order(date(2026, 12, 12))
        order.write({'order_line': [(0, 0, {'product_id': research.id})]})
        order.with_context(gig_conflict_ok=True).action_confirm()
        todo = order.activity_ids.filtered(lambda a: a.summary == "Get the venue's equipment list")
        self.assertEqual(len(todo), 1)
        self.assertIn('Research each piece', str(todo.note))
