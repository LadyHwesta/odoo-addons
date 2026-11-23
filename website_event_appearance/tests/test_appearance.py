# -*- coding: utf-8 -*-
import base64
from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestAppearance(HttpCase):
    """An event someone else runs: listed and linked, never sold here."""

    def setUp(self):
        super().setUp()
        now = fields.Datetime.now()
        self.host = self.env['res.partner'].create({'name': 'The Phoenix Theater'})
        self.flyer = self.env['ir.attachment'].create({
            'name': 'flyer.png', 'mimetype': 'image/png',
            'datas': base64.b64encode(b'\x89PNG\r\n\x1a\n' + b'0' * 32)})
        self.appearance = self.env['event.event'].create({
            'name': 'Friday Night Dance Party', 'is_appearance': True,
            'appearance_host_id': self.host.id, 'appearance_entry': 'tickets',
            'appearance_url': 'https://tickets.example.com/friday',
            'appearance_material_ids': [(6, 0, [self.flyer.id])],
            'date_begin': now + timedelta(days=7), 'date_end': now + timedelta(days=7, hours=4),
            'website_published': True})
        self.own = self.env['event.event'].create({
            'name': 'Our Own Night', 'website_published': True,
            'date_begin': now + timedelta(days=8), 'date_end': now + timedelta(days=8, hours=4)})

    def test_nothing_is_registered_or_sold_here(self):
        self.assertFalse(self.appearance.event_registrations_open)
        self.assertTrue(self.own.event_registrations_open)
        self.assertEqual(self.appearance.appearance_button_label, 'Get tickets')

    def test_event_page_links_to_the_host(self):
        body = self.url_open(f'/event/{self.appearance.id}/register').text
        self.assertIn('https://tickets.example.com/friday', body)
        self.assertIn('Get tickets', body)
        self.assertIn('Hosted by', body)
        self.assertNotIn('Registrations <b>Closed</b>', body)
        self.assertIn(f'/web/image/{self.flyer.id}/256x256', body)

    def test_events_list_shows_the_badge_not_closed(self):
        body = self.url_open('/event').text
        self.assertIn('o_wevent_appearance_badge', body)
        self.assertIn('Performing', body)
        self.assertIn('Friday Night Dance Party', body)
        self.assertIn('Our Own Night', body)

    def test_registration_is_refused_even_if_posted(self):
        response = self.url_open(f'/event/{self.appearance.id}/registration/confirm',
                                 data={'csrf_token': 'x'})
        self.assertIn(response.status_code, (400, 403, 404))

    def test_the_host_is_the_organizer(self):
        self.assertEqual(self.appearance.organizer_id, self.host)

    def test_materials_are_public(self):
        self.assertTrue(self.flyer.public)

    def test_link_rules(self):
        with self.assertRaises(ValidationError):
            self.appearance.appearance_url = False
        with self.assertRaises(ValidationError):
            self.appearance.appearance_url = 'tickets.example.com'
        self.appearance.write({'appearance_entry': 'free', 'appearance_url': False})
        self.assertFalse(self.appearance.appearance_button_label)
        self.assertIn('Free entry', self.url_open(f'/event/{self.appearance.id}/register').text)

    def test_form_shows_only_what_an_appearance_needs(self):
        """Tabs, buttons and fields for running an event are hidden on an
        appearance's form, including tabs from other modules."""
        from lxml import etree
        arch = etree.fromstring(self.env['event.event'].get_views([(False, 'form')])['views']['form']['arch'])
        pages = {page.get('name'): page.get('invisible') or '' for page in arch.xpath('//sheet/notebook/page')}
        self.assertEqual(pages['appearance'], 'not is_appearance')
        self.assertNotIn('is_appearance', pages['event_notes'])
        for name, invisible in pages.items():
            if name not in ('appearance', 'event_notes'):
                self.assertIn('is_appearance', invisible, f"tab {name} should be hidden on an appearance")
        self.assertTrue(arch.xpath("//div[@name='button_box']/field[@widget='website_redirect_button']"))
        for button in arch.xpath("//div[@name='button_box']/*[not(@widget='website_redirect_button')]"):
            self.assertTrue(button.get('invisible') == '1' or 'is_appearance' in (button.get('invisible') or ''))
        for name in ('seats_limited', 'ticket_instructions', 'badge_format'):
            self.assertIn('is_appearance', arch.xpath(f"//field[@name='{name}']")[0].get('invisible'))
        self.assertNotIn('is_appearance', arch.xpath("//field[@name='note']")[0].get('invisible') or '')
