# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, new_test_user, tagged
from odoo.tools import mute_logger

PROVIDER = 'support@provider.example'


@tagged('post_install', '-at_install')
class TestSupportRequest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, mail_create_nolog=True))
        cls.coordinator = new_test_user(
            cls.env, 'sr.coord', groups='base.group_user,support_request_escalation.group_support_coordinator',
            name='Casey Coordinator', email='casey@customer.example')
        cls.staff = new_test_user(cls.env, 'sr.staff', groups='base.group_user', name='Pat Staff',
                                  email='pat@customer.example')
        cls.other = new_test_user(cls.env, 'sr.other', groups='base.group_user', name='Lee Other')
        domain = cls.env['mail.alias.domain'].create({'name': 'customer.example'})
        cls.env.company.alias_domain_id = domain
        cls.ICP = cls.env['ir.config_parameter'].sudo()

    def _report(self, **vals):
        return self.env['support.request'].with_user(self.staff).create({
            'name': "Invoices won't print", 'description': 'Blank page', 'trying_to': 'Print October',
            'page_url': 'https://customer.example/odoo/accounting', 'page_title': 'Invoices', **vals})

    def _set_provider(self):
        self.ICP.set_param('support_request_escalation.email', PROVIDER)
        self.ICP.set_param('support_request_escalation.name', 'Provider Co')

    def test_reporting_reaches_the_coordinators(self):
        request = self._report()
        self.assertTrue(request.reference.startswith('SR'))
        self.assertEqual(request.state, 'new')
        self.assertIn(self.coordinator, request.activity_ids.user_id)
        self.assertIn(self.staff.partner_id, request.message_partner_ids)
        self.assertIn(self.coordinator.partner_id, request.message_partner_ids)

    def test_requests_are_private_to_reporter_and_coordinators(self):
        request = self._report()
        Request = self.env['support.request']
        self.assertFalse(Request.with_user(self.other).search([('id', '=', request.id)]))
        self.assertTrue(Request.with_user(self.coordinator).search([('id', '=', request.id)]))
        self.assertTrue(Request.with_user(self.staff).search([('id', '=', request.id)]))

    def test_only_coordinators_move_it_along(self):
        request = self._report().with_user(self.staff)
        for action in (request.action_take, request.action_solved, request.action_escalate):
            with self.assertRaises(AccessError):
                action()
        with self.assertRaises(AccessError):
            request.write({'state': 'solved'})
        with self.assertRaises(AccessError):
            request.write({'coordinator_id': self.staff.id})
        request.action_close()
        self.assertEqual(request.state, 'closed')

    def test_taking_it_clears_the_others_to_dos(self):
        request = self._report()
        admin_todo = request.activity_ids.filtered(lambda a: a.user_id == self.env.ref('base.user_admin'))
        self.assertTrue(admin_todo, "administrators are coordinators too")
        request.with_user(self.coordinator).action_take()
        self.assertEqual(request.state, 'review')
        self.assertEqual(request.coordinator_id, self.coordinator)
        self.assertEqual(request.activity_ids.user_id, self.coordinator)

    def test_no_provider_no_escalation(self):
        request = self._report()
        self.assertFalse(request.with_user(self.coordinator).can_escalate)
        with self.assertRaises(UserError):
            request.with_user(self.coordinator).action_escalate()

    def test_server_default_from_odoo_conf(self):
        request = self._report()
        server = {'email': PROVIDER, 'name': 'Hosting Co'}
        with patch('odoo.addons.support_request_escalation.models.support_request.server_setting',
                   lambda key: server.get(key, '')):
            request.invalidate_recordset(['can_escalate', 'provider_name'])
            self.assertTrue(request.with_user(self.coordinator).can_escalate)
            self.assertEqual(request.provider_name, 'Hosting Co')
            # This database's own setting wins.
            self.ICP.set_param('support_request_escalation.name', 'Our Partner')
            request.invalidate_recordset(['provider_name'])
            self.assertEqual(request.provider_name, 'Our Partner')

    def _escalate(self, request, note='Tried another browser'):
        action = request.with_user(self.coordinator).action_escalate()
        wizard = self.env['support.request.escalate'].with_user(self.coordinator).with_context(
            action['context']).create({'note': note})
        self.assertEqual(wizard.provider_email, PROVIDER)
        wizard.action_send()

    def test_escalation_emails_the_provider_from_the_catchall(self):
        self._set_provider()
        request = self._report()
        self._escalate(request)
        self.assertEqual(request.state, 'escalated')
        self.assertEqual(request.escalated_by_id, self.coordinator)
        message = request.message_ids.filtered(lambda m: m.subject and request.reference in m.subject)
        self.assertEqual(len(message), 1)
        self.assertIn('Casey Coordinator', message.email_from)
        self.assertIn(self.env.company.catchall_email, message.email_from)
        self.assertIn(f'[support-system {request.get_base_url()} {self.env.cr.dbname}]', message.body)
        self.assertIn('Tried another browser', message.body)
        self.assertIn('Print October', message.body)
        provider = self.env['res.partner'].search([('email', '=', PROVIDER)])
        self.assertIn(provider, message.partner_ids)
        self.assertIn(provider, request.message_partner_ids, "later messages reach the provider too")
        mail = self.env['mail.mail'].sudo().search([('mail_message_id', '=', message.id)])
        self.assertTrue(mail)
        self.assertFalse(request.activity_ids)

    @mute_logger('odoo.addons.mail.models.mail_thread')
    def test_provider_reply_lands_on_the_request(self):
        self._set_provider()
        request = self._report()
        self._escalate(request)
        message = request.message_ids.filtered(lambda m: m.subject and request.reference in m.subject)
        reply = (
            f"From: Provider Support <{PROVIDER}>\r\n"
            f"To: {self.env.company.catchall_email}\r\n"
            f"Subject: Re: [{request.reference}] {request.name}\r\n"
            f"Message-ID: <reply-1@provider.example>\r\n"
            f"In-Reply-To: {message.message_id}\r\n"
            f"References: {message.message_id}\r\n"
            "Content-Type: text/plain; charset=utf-8\r\n\r\n"
            "Fixed: the print layout was missing. Try again?\r\n")
        self.env['mail.thread'].message_process(False, reply)
        self.assertTrue(request.message_ids.filtered(lambda m: 'print layout was missing' in (m.body or '')))
