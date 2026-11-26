# -*- coding: utf-8 -*-
import re

from odoo.exceptions import ValidationError
from odoo.tests.common import HttpCase, tagged
from odoo.tools import mute_logger

BODY = ('<p>Thanks for signing up.</p>'
        '<p><a href="/unsubscribe_from_list">Unsubscribe</a></p>')


@tagged('post_install', '-at_install')
class TestSignupPage(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.news = cls.env['mailing.list'].create({
            'name': 'News and Updates', 'is_public': True, 'signup_page_slug': 'News',
            'signup_page_intro': 'News about new suites, now and then.',
        })
        cls.welcome = cls.env['mailing.mailing'].create({
            'subject': 'Welcome',
            'mailing_model_id': cls.env.ref('mass_mailing.model_mailing_list').id,
            'contact_list_ids': [(4, cls.news.id)],
            'body_html': BODY,
            'email_from': 'hello@example.com',
        })
        cls.news.welcome_mailing_id = cls.welcome

    def _post(self, data, kiosk=False):
        page = self.url_open('/join/news' + ('?kiosk=1' if kiosk else ''))
        token = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
        data = {'csrf_token': token, **data}
        if kiosk:
            data['kiosk'] = '1'
        return self.url_open('/join/news', data=data, allow_redirects=False)

    def _subscriptions(self, email):
        return self.env['mailing.subscription'].search([
            ('list_id', '=', self.news.id), ('contact_id.email', '=', email)])

    def _welcome_mails(self, email):
        return self.env['mail.mail'].sudo().search([
            ('mailing_id', '=', self.welcome.id), ('email_to', 'ilike', email)])

    # -- the list's settings ----------------------------------------------------------

    def test_address_is_cleaned_and_checked(self):
        self.assertEqual(self.news.signup_page_slug, 'news')
        self.assertEqual(self.news.signup_page_url, self.news.get_base_url() + '/join/news')
        self.assertIn('barcode_type=QR', self.news.signup_page_qr_url)
        self.assertIn('%2Fjoin%2Fnews', self.news.signup_page_qr_url)
        with self.assertRaises(ValidationError):
            self.news.signup_page_slug = 'spring fair!'

    def test_only_public_lists_get_a_page(self):
        with self.assertRaises(ValidationError):
            self.env['mailing.list'].create({'name': 'Staff', 'signup_page_slug': 'staff'})

    @mute_logger('odoo.sql_db')
    def test_addresses_are_unique(self):
        with self.assertRaises(Exception):
            self.env['mailing.list'].create({'name': 'Again', 'is_public': True, 'signup_page_slug': 'news'})
            self.env.flush_all()

    # -- the page ------------------------------------------------------------------------

    def test_page_shows_the_form(self):
        page = self.url_open('/join/news')
        self.assertEqual(page.status_code, 200)
        self.assertIn('Nice to meet you!', page.text)
        self.assertIn('News about new suites', page.text)
        self.assertIn('data-captcha="mailing_list_signup"', page.text)
        self.assertIn('autocomplete="email"', page.text)

    def test_unknown_address_is_not_found(self):
        self.assertEqual(self.url_open('/join/nothing-here').status_code, 404)

    def test_signup_subscribes_and_sends_the_welcome_once(self):
        response = self._post({'name': 'Dana Whitfield', 'email': 'Dana@Example.com'})
        self.assertEqual(response.status_code, 303)
        self.assertIn('/join/news?thanks=1', response.headers['Location'])
        subscription = self._subscriptions('dana@example.com')
        self.assertEqual(len(subscription), 1)
        self.assertEqual(subscription.contact_id.name, 'Dana Whitfield')
        self.assertEqual(len(self._welcome_mails('dana@example.com')), 1)
        # Signing up again: still one subscription, still one welcome email.
        self._post({'email': 'dana@example.com'})
        self.assertEqual(len(self._subscriptions('dana@example.com')), 1)
        self.assertEqual(len(self._welcome_mails('dana@example.com')), 1)
        thanks = self.url_open('/join/news?thanks=1')
        self.assertIn('A welcome email is on its way', thanks.text)

    def test_kiosk_forgets_each_person(self):
        page = self.url_open('/join/news?kiosk=1')
        self.assertIn('autocomplete="off"', page.text)
        self.assertNotIn('id="top"', page.text)  # no site header to wander off to
        response = self._post({'email': 'first@example.com'}, kiosk=True)
        self.assertIn('kiosk=1', response.headers['Location'])
        # The next person sees an empty form, not "already subscribed".
        result = self.make_jsonrpc_request('/website_mass_mailing/is_subscriber', {
            'list_id': self.news.id, 'subscription_type': 'email'})
        self.assertFalse(result['value'])
        thanks = self.url_open('/join/news?thanks=1&kiosk=1')
        self.assertIn('Next person', thanks.text)

    def test_bad_address_shows_an_error(self):
        response = self._post({'name': 'Typo', 'email': 'not-an-address'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('look right. Could you check it?', response.text)
        self.assertIn('value="Typo"', response.text)
        self.assertFalse(self.env['mailing.contact'].search([('name', '=', 'Typo')]))

    def test_bots_filling_the_hidden_field_are_ignored(self):
        response = self._post({'email': 'bot@example.com', 'nickname': 'spammy'})
        self.assertIn('thanks=1', response.headers['Location'])
        self.assertFalse(self._subscriptions('bot@example.com'))

    def test_sign_report_renders(self):
        html = self.env['ir.actions.report']._render_qweb_html(
            'mailing_list_signup_page.report_signup_sign', self.news.ids)[0].decode()
        self.assertIn('Scan with your phone', html)
        self.assertIn('/report/barcode/?barcode_type=QR', html)
