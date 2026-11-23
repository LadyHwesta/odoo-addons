# -*- coding: utf-8 -*-
import re
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

CLIENT = 'odoo.addons.signalwire_voip.models.signalwire_server.SignalWireServer._get_client'


@tagged('post_install', '-at_install')
class TestTextedCodes(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        server = cls.env['signalwire.server'].create({
            'name': 'Phones', 'space': 'example.signalwire.com',
            'project_id': 'pid', 'api_token': 'tok'})
        subproject = cls.env['signalwire.subproject'].create({
            'name': 'Internal', 'server_id': server.id, 'account_sid': 'sub', 'state': 'active'})
        cls.sender = cls.env['signalwire.phone_number'].create({
            'name': '+17075550100', 'sid': 'pn-1', 'subproject_id': subproject.id})
        cls.env.company.support_sms_number_id = cls.sender
        cls.customer = cls.env['res.partner'].create({
            'name': 'Pat', 'email': 'pat@example.org', 'phone': '+1 (707) 555-0199'})
        cls.ticket = cls.env['helpdesk.ticket'].create({
            'name': 'Call', 'description': 'x', 'partner_id': cls.customer.id})

    def _send(self):
        client = MagicMock()
        client.compat_post.return_value = {'sid': 'SM1', 'status': 'queued'}
        with patch(CLIENT, return_value=client):
            self.ticket._send_verification_sms()
        return client.compat_post.call_args.kwargs

    def test_code_is_texted_and_verifies(self):
        sent = self._send()
        self.assertEqual(sent['To'], '+1 (707) 555-0199')
        self.assertEqual(sent['From'], '+17075550100')
        code = re.search(r'code: (\d{6})\.', sent['Body']).group(1)
        self.assertTrue(self.ticket._verify_with_code(code))
        self.assertEqual(self.ticket.verification_method, 'sms_code')

    def test_the_code_is_not_kept_anywhere_readable(self):
        sent = self._send()
        code = re.search(r'code: (\d{6})\.', sent['Body']).group(1)
        stored = self.env['signalwire.sms'].search([('to_number', '=', '+1 (707) 555-0199')])
        self.assertTrue(stored)
        self.assertNotIn(code, stored.body)
        texts = ' '.join(filter(None, (self.ticket.message_ids | self.customer.message_ids).mapped('body')))
        self.assertNotIn(code, texts)
        self.assertIn('0199', texts)

    def test_support_mobile_wins_over_phone(self):
        self.customer.support_mobile = '+17075550123'
        self.assertEqual(self._send()['To'], '+17075550123')

    def test_three_texts_an_hour(self):
        for _i in range(3):
            self._send()
        with self.assertRaises(UserError):
            self._send()

    def test_a_contact_who_replied_stop_is_not_texted(self):
        self.customer.sms_blocked = True
        with self.assertRaises(UserError):
            self._send()

    def test_no_sender_number_means_no_texting(self):
        self.env.company.support_sms_number_id = False
        self.assertEqual(self.ticket._verification_sms_number(), '')
        with self.assertRaises(UserError):
            self.ticket._send_verification_sms()

    def test_wizard_offers_texting_and_masks_the_number(self):
        wizard = self.env['helpdesk.ticket.verify'].create({'ticket_id': self.ticket.id})
        self.assertTrue(wizard.can_text)
        self.assertEqual(wizard.text_destination, '•••• 0199')
