# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSignalWireSms(TransactionCase):

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
            'name': 'Jane Customer', 'phone': '+1 (555) 610-2107',
        })

    def _sms(self, direction, **vals):
        base = {
            'phone_number_id': self.number.id, 'direction': direction,
            'from_number': '+15556102107', 'to_number': '+12084449665',
            'body': 'hello', 'state': 'received',
        }
        base.update(vals)
        return self.env['signalwire.sms'].create(base)

    def test_log_to_partner_chatter_matches_by_last_ten_digits(self):
        message = self._sms('inbound', from_number='+15556102107', to_number='+12084449665')

        message._log_to_partner_chatter()

        self.assertEqual(message.partner_id, self.partner)
        self.assertTrue(any(
            'hello' in (msg.body or '') for msg in self.partner.message_ids))

    def test_log_to_partner_chatter_no_match_leaves_partner_blank(self):
        message = self._sms('inbound', from_number='+19995551234', to_number='+12084449665')

        message._log_to_partner_chatter()

        self.assertFalse(message.partner_id)

    def test_outbound_message_matches_by_the_to_number(self):
        message = self._sms(
            'outbound', from_number='+12084449665', to_number='+15556102107')

        message._log_to_partner_chatter()

        self.assertEqual(message.partner_id, self.partner)

    def test_forward_to_webhook_posts_the_message_json(self):
        self.number.sms_webhook_url = 'https://customer.example.com/hook'
        message = self._sms('inbound')

        with patch('requests.post') as post:
            post.return_value = MagicMock(status_code=200)
            message._forward_to_customer_webhook()

        args, kwargs = post.call_args
        self.assertEqual(args[0], 'https://customer.example.com/hook')
        self.assertEqual(kwargs['json']['body'], 'hello')
        self.assertEqual(message.webhook_status, 'forwarded')

    def test_forward_without_a_webhook_configured_does_nothing(self):
        message = self._sms('inbound')

        with patch('requests.post') as post:
            message._forward_to_customer_webhook()

        post.assert_not_called()
        self.assertFalse(message.webhook_status)

    def test_forward_failure_is_logged_not_raised(self):
        import requests
        self.number.sms_webhook_url = 'https://customer.example.com/hook'
        message = self._sms('inbound')

        with patch('requests.post', side_effect=requests.ConnectionError('boom')):
            message._forward_to_customer_webhook()  # should not raise

        self.assertIn('boom', message.webhook_status)
