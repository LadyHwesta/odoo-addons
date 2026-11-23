# -*- coding: utf-8 -*-
import base64
import io
from datetime import timedelta

from PIL import Image

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import HttpCase, tagged


def png(width, height):
    buf = io.BytesIO()
    Image.new('RGB', (width, height), (200, 40, 120)).save(buf, format='PNG')
    return base64.b64encode(buf.getvalue())


@tagged('post_install', '-at_install')
class TestPressKit(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.website = cls.env['website'].get_current_website()
        # A database that already has a press kit (only inside this test's transaction).
        cls.env['website.press.kit'].search([('website_id', '=', cls.website.id)]).unlink()
        cls.kit = cls.env['website.press.kit'].create({
            'website_id': cls.website.id, 'is_published': True, 'name': 'DJ Nova',
            'tagline': 'Open-format DJ for weddings and clubs', 'bio': '<p>Spinning since 2009.</p>',
            'genres': 'House, Disco , ,Top 40', 'based_in': 'Sonoma County',
            'booking_email': 'book@example.com',
            'photo_ids': [(0, 0, {'image_full': png(3000, 2000), 'caption': 'At the decks', 'credit': 'Sam Lens'})],
            'link_ids': [(0, 0, {'kind': 'mix', 'label': 'Summer mix', 'url': 'https://mixes.example/summer'})],
        })
        now = fields.Datetime.now()
        Event = cls.env['event.event']
        cls.coming = Event.create({'name': 'Rooftop Night', 'date_begin': now + timedelta(days=10),
                                   'date_end': now + timedelta(days=10, hours=4), 'website_published': True})
        cls.past = Event.create({'name': 'Last Year Party', 'date_begin': now - timedelta(days=30),
                                 'date_end': now - timedelta(days=30) + timedelta(hours=4), 'website_published': True})
        cls.draft = Event.create({'name': 'Secret Show', 'date_begin': now + timedelta(days=5),
                                  'date_end': now + timedelta(days=5, hours=3), 'website_published': False})

    def test_the_page_shows_the_kit(self):
        response = self.url_open('/press-kit')
        self.assertEqual(response.status_code, 200)
        for text in ('DJ Nova', 'Open-format DJ', 'Spinning since 2009', 'Sonoma County', 'book@example.com',
                     '>House<', '>Top 40<', 'Summer mix', 'https://mixes.example/summer', 'At the decks',
                     'Sam Lens', 'href="/book"'):
            self.assertIn(text, response.text)
        self.assertEqual(self.kit.genre_list(), ['House', 'Disco', 'Top 40'])

    def test_upcoming_published_events_only(self):
        html = self.url_open('/press-kit').text
        self.assertIn('Rooftop Night', html)
        self.assertNotIn('Last Year Party', html)
        self.assertNotIn('Secret Show', html)
        self.kit.show_events = False
        self.assertNotIn('Rooftop Night', self.url_open('/press-kit').text)

    def test_unpublished_kit_is_not_found(self):
        self.kit.is_published = False
        self.assertEqual(self.url_open('/press-kit').status_code, 404)
        photo = self.kit.photo_ids
        self.assertEqual(self.url_open(f'/press-kit/photo/{photo.id}').status_code, 404)

    def test_photos_show_small_and_download_full_size(self):
        photo = self.kit.photo_ids
        shown = self.url_open(f'/press-kit/photo/{photo.id}')
        self.assertEqual(shown.status_code, 200)
        self.assertEqual(Image.open(io.BytesIO(shown.content)).size[0], 1024)
        full = self.url_open(f'/press-kit/photo/{photo.id}?download=1')
        self.assertEqual(Image.open(io.BytesIO(full.content)).size, (3000, 2000))
        self.assertIn('attachment', full.headers.get('Content-Disposition', ''))

    def test_another_websites_photos_stay_private(self):
        other_site = self.env['website'].create({'name': 'Other', 'domain': 'other.example'})
        other_kit = self.env['website.press.kit'].create({
            'website_id': other_site.id, 'is_published': True, 'name': 'Other Act',
            'photo_ids': [(0, 0, {'image_full': png(50, 50)})]})
        self.assertEqual(self.url_open(f'/press-kit/photo/{other_kit.photo_ids.id}').status_code, 404)

    def test_rider_download(self):
        self.assertEqual(self.url_open('/press-kit/rider').status_code, 404)
        self.kit.write({'rider': base64.b64encode(b'%PDF-1.4 rider'), 'rider_filename': 'rider.pdf'})
        response = self.url_open('/press-kit/rider')
        self.assertEqual(response.content, b'%PDF-1.4 rider')
        self.assertIn('rider.pdf', response.headers.get('Content-Disposition', ''))

    def test_links_must_be_web_addresses(self):
        with self.assertRaises(ValidationError):
            self.env['website.press.kit.link'].create({
                'kit_id': self.kit.id, 'label': 'Bad', 'url': 'javascript:alert(1)'})
        with self.assertRaises(ValidationError):
            self.kit.book_url = 'javascript:alert(1)'

    def test_one_kit_per_website(self):
        with self.assertRaises(Exception), self.cr.savepoint():
            self.env['website.press.kit'].create({'website_id': self.website.id, 'name': 'Second'})
