# -*- coding: utf-8 -*-
import re
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestSongRequests(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = cls.env['res.partner'].create({'name': 'Maya & Jordan', 'email': 'maya@example.com'})
        cls.product = cls.env['product.product'].create({
            'name': 'DJ package', 'type': 'service', 'list_price': 800, 'taxes_id': [(5, 0, 0)]})
        cls.gig = cls._make_gig(fields.Date.today() + timedelta(days=30))

    @classmethod
    def _make_gig(cls, day, confirm=True, **extra):
        order = cls.env['sale.order'].create({**extra,
            'partner_id': cls.client.id, 'gig_date': day, 'gig_start_hour': 18.0, 'gig_end_hour': 23.0,
            'venue_name': 'Ledson Winery', 'order_line': [(0, 0, {'product_id': cls.product.id})]})
        if confirm:
            order.with_context(gig_conflict_ok=True).action_confirm()
        return order

    def _page(self, url):
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200)
        return response.text

    def _csrf(self, html):
        # A closed or locked page has no form: any page's token is the session's.
        found = re.search(r'name="csrf_token" value="([^"]+)"', html) or re.search(
            r'name="csrf_token" value="([^"]+)"', self._page('/web/login'))
        return found.group(1)

    def _request(self, order, song, **extra):
        url = f'/gig/{order.sudo().song_request_token}/songs'
        data = {'csrf_token': self._csrf(self._page(url)), 'song': song, **extra}
        return self.url_open(url, data=data)

    def _guest_songs(self, order):
        return order.song_request_ids.filtered(lambda r: r.kind == 'request').mapped('song')

    # ---- guests ----

    def test_a_guest_requests_a_song(self):
        response = self._request(self.gig, '  September ', artist='Earth, Wind & Fire', name='Gran')
        self.assertIn('Your request is on the list', response.text)
        line = self.gig.song_guest_ids
        self.assertEqual((line.song, line.artist, line.requested_by, line.state),
                         ('September', 'Earth, Wind & Fire', 'Gran', 'new'))

    def test_one_phone_cant_flood_the_list(self):
        for n in range(5):
            self._request(self.gig, f'Song {n}')
        response = self._request(self.gig, 'Song 6')
        self.assertIn('sent a few already', response.text)
        self.assertEqual(len(self._guest_songs(self.gig)), 5)

    def test_bots_filling_the_hidden_field_are_ignored(self):
        self._request(self.gig, 'Spam', website_url='http://spam.example')
        self.assertFalse(self._guest_songs(self.gig))

    def test_requests_close_when_the_gig_ends(self):
        past = self._make_gig(fields.Date.today() - timedelta(days=2))
        self.assertIn('Song requests are closed', self._request(past, 'Too late').text)
        self.assertFalse(self._guest_songs(past))

    def test_closed_until_booked_and_when_turned_off(self):
        quote = self._make_gig(fields.Date.today() + timedelta(days=60), confirm=False)
        self.assertIn('closed', self._request(quote, 'Early').text)
        self.gig.song_requests_enabled = False
        self.assertIn('closed', self._request(self.gig, 'Off').text)
        self.assertFalse(self._guest_songs(quote) + self._guest_songs(self.gig))

    def test_unknown_link_is_not_found(self):
        self.assertEqual(self.url_open('/gig/not-a-real-token/songs').status_code, 404)

    def test_do_not_play_requests_are_flagged(self):
        self.env['gig.song.request'].create({'order_id': self.gig.id, 'kind': 'do_not_play',
                                             'song': 'Cha Cha Slide'})
        self._request(self.gig, 'cha-cha slide!')
        self._request(self.gig, 'September')
        flagged = self.gig.song_guest_ids.filtered('on_do_not_play')
        self.assertEqual(flagged.mapped('song'), ['cha-cha slide!'])

    # ---- the link ----

    def test_link_uses_the_gigs_own_website(self):
        other = self.env['res.company'].create({'name': 'DJ Company'})
        self.env['website'].create({'name': 'DJ site', 'domain': 'djexample.com', 'company_id': other.id})
        gig = self._make_gig(fields.Date.today() + timedelta(days=45), company_id=other.id)
        self.assertNotEqual(gig.sudo().song_request_token, self.gig.sudo().song_request_token)
        self.assertEqual(gig.song_request_url, f'https://djexample.com/gig/{gig.sudo().song_request_token}/songs')

    # ---- the client's lists ----

    def _portal(self, order):
        return self._page(order.get_portal_url(suffix='/music'))

    def _client_post(self, order, **data):
        html = self._portal(order)
        data.update(csrf_token=self._csrf(html), access_token=order.access_token)
        return self.url_open(f'/my/orders/{order.id}/music', data=data)

    def test_client_builds_their_lists_from_the_portal(self):
        self.assertIn('Music for your event', self._page(self.gig.get_portal_url()))
        self._client_post(self.gig, kind='must_play', song='At Last', artist='Etta James', note='First dance')
        self._client_post(self.gig, kind='do_not_play', song='Macarena')
        self.assertEqual((self.gig.song_must_ids.song, self.gig.song_must_ids.note), ('At Last', 'First dance'))
        self.assertEqual(self.gig.song_never_ids.song, 'Macarena')
        self.assertIn('At Last', self._portal(self.gig))
        self._client_post(self.gig, remove=str(self.gig.song_never_ids.id))
        self.assertFalse(self.gig.song_never_ids)

    def test_client_cant_touch_guest_requests_or_other_gigs(self):
        other = self._make_gig(fields.Date.today() + timedelta(days=90))
        theirs = self.env['gig.song.request'].create({'order_id': other.id, 'kind': 'must_play', 'song': 'X'})
        guest = self.env['gig.song.request'].create({'order_id': self.gig.id, 'kind': 'request', 'song': 'Y'})
        self._client_post(self.gig, remove=str(theirs.id))
        self._client_post(self.gig, remove=str(guest.id))
        self._client_post(self.gig, kind='request', song='Sneaky')
        self.assertTrue(theirs.exists() and guest.exists())
        self.assertEqual(self._guest_songs(self.gig), ['Y'])

    def test_lists_lock_when_the_gig_starts(self):
        started = self._make_gig(fields.Date.today() - timedelta(days=1))
        self.assertIn('locked', self._client_post(started, kind='must_play', song='Late').text)
        self.assertFalse(started.song_must_ids)

    # ---- printouts ----

    def test_card_and_load_in_sheet(self):
        self.env['gig.song.request'].create([
            {'order_id': self.gig.id, 'kind': 'must_play', 'song': 'At Last', 'note': 'First dance'},
            {'order_id': self.gig.id, 'kind': 'do_not_play', 'song': 'Macarena'}])
        Report = self.env['ir.actions.report']
        card = Report._render_qweb_html('sale_gig_song_requests.report_song_card', self.gig.ids)[0].decode()
        self.assertIn(self.gig.sudo().song_request_token, card)
        self.assertIn('data:image/png;base64,', card)
        sheet = Report._render_qweb_html('sale_gig_booking.report_gig_load_in', self.gig.ids)[0].decode()
        self.assertIn('Request a song', sheet)
        self.assertIn('data:image/png;base64,', sheet)
        self.assertNotIn('Macarena', sheet)  # song lists aren't printed: they're worked online
        self.gig.song_requests_enabled = False
        sheet = Report._render_qweb_html('sale_gig_booking.report_gig_load_in', self.gig.ids)[0].decode()
        self.assertNotIn('Request a song', sheet)

    # ---- getting the tracks ----

    def test_got_it_and_cant_get_with_a_reason(self):
        must = self.env['gig.song.request'].create(
            {'order_id': self.gig.id, 'kind': 'must_play', 'song': 'Rare Remix', 'note': 'First dance'})
        guest = self.env['gig.song.request'].create({'order_id': self.gig.id, 'kind': 'request', 'song': 'Hit'})
        guest.action_got_it()
        self.assertEqual(guest.acquire_state, 'got')
        action = must.action_cant_get()
        self.assertEqual((action['res_id'], action['target']), (must.id, 'new'))
        with self.assertRaises(UserError):
            must.action_confirm_cant_get()  # no reason given
        must.acquire_note = 'Only a live bootleg exists'
        must.action_confirm_cant_get()
        self.assertEqual(must.acquire_state, 'unavailable')
        self.assertIn("Can't get this one", self._portal(self.gig))
        self.assertIn('Only a live bootleg exists', self._portal(self.gig))
        must.action_reset_acquire()
        self.assertEqual((must.acquire_state, must.acquire_note), ('to_get', False))

    def test_songs_to_get_lists_must_play_and_requests_only(self):
        R = self.env['gig.song.request']
        R.create([{'order_id': self.gig.id, 'kind': k, 'song': k} for k in ('must_play', 'request', 'do_not_play')])
        action = self.env.ref('sale_gig_song_requests.action_gig_song_to_get')
        found = R.search(eval(action.domain) + [('order_id', '=', self.gig.id)])
        self.assertEqual(sorted(found.mapped('kind')), ['must_play', 'request'])
