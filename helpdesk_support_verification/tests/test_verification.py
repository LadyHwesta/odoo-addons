# -*- coding: utf-8 -*-
import re
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import HttpCase, TransactionCase, new_test_user, tagged


class VerificationCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Codes = cls.env['support.verification.code']
        cls.customer = cls.env['res.partner'].create({'name': 'Pat Customer', 'email': 'pat@example.org'})
        cls.other = cls.env['res.partner'].create({'name': 'Someone Else', 'email': 'else@example.org'})
        cls.agent = new_test_user(cls.env, login='agent', groups='helpdesk_mgmt.group_helpdesk_user')
        cls.in_progress = cls.env.ref('helpdesk_mgmt.helpdesk_ticket_stage_in_progress')
        cls.cancelled = cls.env.ref('helpdesk_mgmt.helpdesk_ticket_stage_cancelled')

    def _ticket(self, partner=None):
        return self.env['helpdesk.ticket'].with_user(self.agent).create({
            'name': 'Mailbox not receiving', 'description': 'x',
            'partner_id': (partner or self.customer).id})


@tagged('post_install', '-at_install')
class TestVerification(VerificationCase):

    def test_new_ticket_is_unverified_and_cannot_be_worked(self):
        ticket = self._ticket()
        self.assertEqual(ticket.verification_state, 'unverified')
        with self.assertRaises(UserError):
            ticket.with_user(self.agent).stage_id = self.in_progress

    def test_customers_and_automatic_moves_are_not_blocked(self):
        ticket = self._ticket()
        portal = new_test_user(self.env, login='pat2', groups='base.group_portal',
                               partner_id=self.customer.id)
        done = self.env.ref('helpdesk_mgmt.helpdesk_ticket_stage_done')
        # The portal's Close button writes in sudo as the customer.
        ticket.with_user(portal).sudo().stage_id = done
        self.assertEqual(ticket.stage_id, done)
        other = self._ticket()
        other.sudo().stage_id = self.in_progress
        self.assertEqual(other.stage_id, self.in_progress)

    def test_it_can_be_cancelled_unverified(self):
        ticket = self._ticket()
        ticket.stage_id = self.cancelled
        self.assertEqual(ticket.stage_id, self.cancelled)

    def test_support_key_verifies_once(self):
        key, _expires = self.Codes._issue(self.customer, 'support_key')
        self.assertRegex(key, r'^[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}$')
        self.assertNotRegex(key, r'[01OIL]')
        ticket = self._ticket()
        self.assertTrue(ticket.with_user(self.agent)._verify_with_code(key.lower().replace('-', ' ')))
        self.assertEqual(ticket.verification_state, 'verified')
        self.assertEqual(ticket.verification_method, 'support_key')
        self.assertEqual(ticket.verified_by_id, self.agent)
        ticket.stage_id = self.in_progress
        # Used up: it doesn't verify a second ticket.
        self.assertFalse(self._ticket()._verify_with_code(key))

    def test_code_is_never_stored_or_logged(self):
        key, _expires = self.Codes._issue(self.customer, 'support_key')
        ticket = self._ticket()
        ticket._verify_with_code(key)
        bare = key.replace('-', '')
        record = self.Codes.search([('partner_id', '=', self.customer.id)])
        self.assertNotIn(bare, record.code_hash)
        for body in ticket.message_ids.mapped('body'):
            self.assertNotIn(key, body or '')
            self.assertNotIn(bare, body or '')

    def test_another_customers_key_does_not_work(self):
        key, _expires = self.Codes._issue(self.other, 'support_key')
        ticket = self._ticket()
        self.assertFalse(ticket._verify_with_code(key))
        self.assertEqual(ticket.verification_state, 'unverified')

    def test_expired_key_does_not_work(self):
        key, _expires = self.Codes._issue(self.customer, 'support_key')
        self.Codes.search([('partner_id', '=', self.customer.id)]).expires_at = \
            fields.Datetime.now() - timedelta(minutes=1)
        self.assertFalse(self._ticket()._verify_with_code(key))

    def test_a_new_key_replaces_the_old_one(self):
        old, _expires = self.Codes._issue(self.customer, 'support_key')
        new, _expires = self.Codes._issue(self.customer, 'support_key')
        ticket = self._ticket()
        self.assertFalse(ticket._verify_with_code(old))
        self.assertTrue(ticket._verify_with_code(new))

    def test_five_wrong_codes_lock_the_ticket(self):
        key, _expires = self.Codes._issue(self.customer, 'support_key')
        ticket = self._ticket()
        for _attempt in range(5):
            self.assertFalse(ticket._verify_with_code('AAAA-BBBB-CCCC'))
        with self.assertRaises(UserError):
            ticket._verify_with_code(key)

    def test_a_different_contact_must_be_verified_again(self):
        key, _expires = self.Codes._issue(self.customer, 'support_key')
        ticket = self._ticket()
        ticket._verify_with_code(key)
        ticket.partner_id = self.other
        self.assertEqual(ticket.verification_state, 'unverified')

    def test_general_question_can_skip_verification(self):
        ticket = self._ticket()
        ticket.with_user(self.agent).action_mark_verification_not_needed()
        self.assertEqual(ticket.verification_state, 'not_needed')
        ticket.with_user(self.agent).stage_id = self.in_progress

    def test_ticket_without_contact_needs_one_first(self):
        ticket = self.env['helpdesk.ticket'].create({'name': 'From a stranger', 'description': 'x'})
        with self.assertRaises(UserError):
            ticket._verify_with_code('AAAA-BBBB-CCCC')

    def test_wizard_verifies(self):
        key, _expires = self.Codes._issue(self.customer, 'support_key')
        ticket = self._ticket()
        wizard = self.env['helpdesk.ticket.verify'].with_user(self.agent).create(
            {'ticket_id': ticket.id, 'code': key})
        wizard.action_verify()
        self.assertEqual(ticket.verification_state, 'verified')
        self.assertFalse(wizard.can_text, 'no texting without the SMS add-on')

    def test_portal_customer_ticket_is_verified(self):
        portal = new_test_user(self.env, login='pat', groups='base.group_portal',
                               partner_id=self.customer.id)
        ticket = self.env['helpdesk.ticket'].with_user(portal).sudo().create(
            {'name': 'From the portal', 'description': 'x'})
        self.assertEqual(ticket.partner_id, self.customer)
        self.assertEqual(ticket.verification_method, 'portal')

    def test_anonymous_visitor_ticket_is_not_verified(self):
        public = self.env.ref('base.public_user')
        ticket = self.env['helpdesk.ticket'].with_user(public).sudo().create(
            {'name': 'From the website', 'description': 'x'})
        self.assertEqual(ticket.verification_state, 'unverified')

    def test_stage_setup(self):
        self.assertFalse(self.env.ref('helpdesk_mgmt.helpdesk_ticket_stage_new').requires_verification)
        self.assertFalse(self.cancelled.requires_verification)
        self.assertTrue(self.in_progress.requires_verification)
        self.assertTrue(self.env.ref('helpdesk_mgmt.helpdesk_ticket_stage_done').requires_verification)


@tagged('post_install', '-at_install')
class TestSupportKeyPortal(HttpCase):

    def test_customer_gets_a_key_that_verifies(self):
        customer = self.env['res.partner'].create({'name': 'Pat', 'email': 'pat@example.org'})
        new_test_user(self.env, login='patportal', password='patportal123',
                      groups='base.group_portal', partner_id=customer.id)
        self.authenticate('patportal', 'patportal123')
        page = self.url_open('/my/support-key')
        self.assertEqual(page.status_code, 200)
        self.assertIn('Get a support key', page.text)
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
        response = self.url_open('/my/support-key', data={'csrf_token': csrf})
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response.headers.get('Cache-Control', ''))
        key = re.search(r'o_support_key_value[^>]*>([A-Z2-9-]{14})<', response.text).group(1)
        ticket = self.env['helpdesk.ticket'].create(
            {'name': 'Call', 'description': 'x', 'partner_id': customer.id})
        self.assertTrue(ticket._verify_with_code(key))

    def test_signed_out_visitors_are_sent_to_login(self):
        response = self.url_open('/my/support-key', allow_redirects=False)
        self.assertIn(response.status_code, (302, 303))
        self.assertIn('/web/login', response.headers.get('Location', ''))
