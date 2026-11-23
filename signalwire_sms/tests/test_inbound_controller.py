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

    def test_delivery_reports_update_sent_texts_only(self):
        sent = self.env['signalwire.sms'].create({
            'phone_number_id': self.number.id, 'direction': 'outbound', 'sid': 'SM-out',
            'from_number': '+12084449665', 'to_number': '+15556102107',
            'body': 'hello', 'state': 'queued'})
        response = self.url_open('/signalwire/sms/status', data={
            'MessageSid': 'SM-out', 'MessageStatus': 'delivered'})
        self.assertEqual(response.status_code, 204)
        self.assertEqual(sent.state, 'delivered')

        self.url_open('/signalwire/sms/status', data={
            'MessageSid': 'SM-out', 'MessageStatus': 'undelivered', 'ErrorCode': '30007'})
        self.assertEqual(sent.state, 'undelivered (30007)')

        self.url_open('/signalwire/sms/status', data={
            'MessageSid': 'SM-unknown', 'MessageStatus': 'failed'})
        self.assertEqual(self.env['signalwire.sms'].search_count([('state', '=', 'failed')]), 0)

    # --- Signature checks on a real webhook --------------------------------

    def _signed_post(self, path, data, key=None, signature=None):
        from odoo.addons.signalwire_voip import webhook_security
        url = self.base_url() + path
        if signature is None and key:
            signature = webhook_security.compute_signature(key, url, sorted(data.items()))
        headers = {'X-SignalWire-Signature': signature} if signature else {}
        return self.url_open(path, data=data, headers=headers)

    def _inbound(self, sid):
        return {'To': '+12084449665', 'From': '+15556102107', 'Body': 'hi', 'MessageSid': sid}

    def test_unsigned_texts_are_accepted_and_logged_until_rejecting_is_on(self):
        self.env['ir.config_parameter'].sudo().set_param('web.base.url', self.base_url())
        self.server.signing_key = 'PSK-test'
        with self.assertLogs('odoo.addons.signalwire_voip.models.signalwire_server', 'WARNING'):
            response = self._signed_post('/signalwire/sms/inbound', self._inbound('SM-1'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.env['signalwire.sms'].search([('sid', '=', 'SM-1')]))
        self.assertEqual(self.server.webhook_last_invalid_path, '/signalwire/sms/inbound')

    def test_rejecting_refuses_bad_signatures_and_keeps_good_ones(self):
        self.env['ir.config_parameter'].sudo().set_param('web.base.url', self.base_url())
        self.server.write({'signing_key': 'PSK-test', 'webhook_signature_mode': 'enforce'})

        good = self._signed_post('/signalwire/sms/inbound', self._inbound('SM-good'), key='PSK-test')
        self.assertEqual(good.status_code, 200)
        self.assertTrue(self.env['signalwire.sms'].search([('sid', '=', 'SM-good')]))

        bad = self._signed_post('/signalwire/sms/inbound', self._inbound('SM-bad'), key='wrong-key')
        missing = self._signed_post('/signalwire/sms/inbound', self._inbound('SM-none'))
        self.assertEqual((bad.status_code, missing.status_code), (403, 403))
        self.assertFalse(self.env['signalwire.sms'].search([('sid', 'in', ['SM-bad', 'SM-none'])]))

    def test_a_subprojects_own_key_is_accepted_too(self):
        self.env['ir.config_parameter'].sudo().set_param('web.base.url', self.base_url())
        self.server.write({'signing_key': 'PSK-main', 'webhook_signature_mode': 'enforce'})
        self.subproject.signing_key = 'PSK-sub'
        response = self._signed_post('/signalwire/sms/inbound', self._inbound('SM-sub'), key='PSK-sub')
        self.assertEqual(response.status_code, 200)
