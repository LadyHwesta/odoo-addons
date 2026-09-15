# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestInboundSmsController(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'project_id': 'pid123', 'api_token': 'tok456',
        })
        cls.subproject = cls.env['signalwire.subproject'].create({
            'name': 'Internal Team', 'server_id': cls.server.id,
            'account_sid': 'sub-abc', 'state': 'active',
        })
        cls.number = cls.env['signalwire.phone_number'].create({
            'name': '+12084449665', 'sid': 'pn-123', 'subproject_id': cls.subproject.id,
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'Jane Customer', 'phone': '+15556102107',
        })

    def test_inbound_sms_creates_a_message_record(self):
        response = self.url_open('/signalwire/sms/inbound', data={
            'To': '+12084449665', 'From': '+15556102107',
            'Body': 'hello from a customer', 'MessageSid': 'sms-in-1',
        })

        self.assertEqual(response.status_code, 200)
        message = self.env['signalwire.sms'].search([('sid', '=', 'sms-in-1')])
        self.assertTrue(message)
        self.assertEqual(message.direction, 'inbound')
        self.assertEqual(message.body, 'hello from a customer')

    def test_inbound_sms_logs_to_the_matched_partners_chatter(self):
        self.url_open('/signalwire/sms/inbound', data={
            'To': '+12084449665', 'From': '+15556102107',
            'Body': 'logged to chatter', 'MessageSid': 'sms-in-2',
        })

        self.assertTrue(any(
            'logged to chatter' in (msg.body or '') for msg in self.partner.message_ids))

    def test_inbound_sms_to_an_unknown_number_does_not_crash(self):
        response = self.url_open('/signalwire/sms/inbound', data={
            'To': '+19995550000', 'From': '+15556102107',
            'Body': 'nobody home', 'MessageSid': 'sms-in-3',
        })
        self.assertEqual(response.status_code, 200)

    def test_inbound_sms_forwards_to_configured_webhook(self):
        self.number.sms_webhook_url = 'https://customer.example.com/hook'
        with patch('requests.post') as post:
            self.url_open('/signalwire/sms/inbound', data={
                'To': '+12084449665', 'From': '+15556102107',
                'Body': 'forward me', 'MessageSid': 'sms-in-4',
            })
        post.assert_called_once()
        self.assertEqual(post.call_args.args[0], 'https://customer.example.com/hook')
