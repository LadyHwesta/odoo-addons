# -*- coding: utf-8 -*-
from odoo.exceptions import ValidationError
from odoo.tests.common import HttpCase, tagged

BODY = ('<p>Thanks for signing up. We will write once, when it is ready.</p>'
        '<p><a href="/unsubscribe_from_list">Unsubscribe</a></p>')


@tagged('post_install', '-at_install')
class TestWelcomeEmail(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.launch_list = cls.env['mailing.list'].create({'name': 'Odoo hosting launch'})
        cls.other_list = cls.env['mailing.list'].create({'name': 'Other'})
        cls.welcome = cls.env['mailing.mailing'].create({
            'subject': "You're on the list",
            'mailing_model_id': cls.env.ref('mass_mailing.model_mailing_list').id,
            'contact_list_ids': [(4, cls.launch_list.id)],
            'body_html': BODY,
            'email_from': 'hello@example.com',
        })
        cls.launch_list.welcome_mailing_id = cls.welcome

    def _subscribe(self, email, mailing_list=None):
        return self.make_jsonrpc_request('/website_mass_mailing/subscribe', {
            'list_id': (mailing_list or self.launch_list).id,
            'value': email,
            'subscription_type': 'email',
        })

    def _welcome_mails(self, email):
        return self.env['mail.mail'].sudo().search([
            ('mailing_id', '=', self.welcome.id), ('email_to', 'ilike', email)])

    def test_signup_gets_one_welcome_email_with_its_own_unsubscribe_link(self):
        result = self._subscribe('newperson@example.com')
        self.assertEqual(result['toast_type'], 'success')
        mails = self._welcome_mails('newperson@example.com')
        self.assertEqual(len(mails), 1)
        self.assertIn('/unsubscribe_from_list', mails.body_html)
        # What actually goes out: the link made personal, plus one-click headers.
        outgoing = mails._prepare_outgoing_list()[0]
        self.assertIn('confirm_unsubscribe', outgoing['body'])
        self.assertIn('hash_token', outgoing['body'])
        self.assertIn('List-Unsubscribe', outgoing['headers'])
        # The mailing itself stays a draft, ready for the next signup.
        self.assertNotEqual(self.welcome.state, 'done')

    def test_the_same_address_never_gets_it_twice(self):
        self._subscribe('repeat@example.com')
        self._subscribe('repeat@example.com')
        subscription = self.env['mailing.subscription'].search([
            ('list_id', '=', self.launch_list.id), ('contact_id.email', '=', 'repeat@example.com')])
        subscription.opt_out = True
        self._subscribe('repeat@example.com')  # re-joins after leaving
        self.assertEqual(len(self._welcome_mails('repeat@example.com')), 1)

    def test_blocklisted_address_gets_nothing(self):
        self.env['mail.blacklist'].create({'email': 'blocked@example.com'})
        self._subscribe('blocked@example.com')
        sent = self._welcome_mails('blocked@example.com').filtered(lambda m: m.state != 'cancel')
        self.assertFalse(sent)

    def test_lists_without_a_welcome_email_send_nothing(self):
        self._subscribe('quiet@example.com', self.other_list)
        self.assertFalse(self.env['mail.mail'].sudo().search([('email_to', 'ilike', 'quiet@example.com')]))

    def test_welcome_email_must_have_an_unsubscribe_link(self):
        with self.assertRaises(ValidationError):
            self.welcome.body_html = '<p>No way out</p>'
            self.launch_list.welcome_mailing_id = self.welcome

    def test_welcome_email_must_be_addressed_to_the_list(self):
        with self.assertRaises(ValidationError):
            self.other_list.welcome_mailing_id = self.welcome
