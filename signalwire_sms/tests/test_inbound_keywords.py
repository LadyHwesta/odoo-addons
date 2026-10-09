# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestInboundKeywords(HttpCase):

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

    def setUp(self):
        super().setUp()
        self.signalwire_client = MagicMock()
        self.signalwire_client.compat_post.return_value = {'sid': 'sms-reply', 'status': 'queued'}
        patcher = patch(
            'odoo.addons.signalwire_voip.models.signalwire_server.'
            'SignalWireServer._get_client', return_value=self.signalwire_client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _inbound(self, body, message_sid='sms-in-1'):
        return self.url_open('/signalwire/sms/inbound', data={
            'To': '+12084449665', 'From': '+15556102107',
            'Body': body, 'MessageSid': message_sid,
        })

    def test_stop_blocks_the_matched_partner(self):
        self._inbound('STOP')
        self.assertTrue(self.partner.sms_blocked)

    def test_stop_is_case_and_whitespace_insensitive(self):
        self._inbound('  stop  ')
        self.assertTrue(self.partner.sms_blocked)

    def test_stop_family_keyword_also_blocks(self):
        self._inbound('unsubscribe')
        self.assertTrue(self.partner.sms_blocked)

    def test_stop_sends_a_confirmation_reply(self):
        self._inbound('STOP')
        self.signalwire_client.compat_post.assert_called_once_with(
            'Accounts/sub-abc/Messages.json',
            From='+12084449665', To='+15556102107',
            Body=self.number.sms_stop_reply_text)

    def test_start_unblocks_the_partner(self):
        self.partner.sms_blocked = True
        self._inbound('START')
        self.assertFalse(self.partner.sms_blocked)

    def test_help_sends_a_reply_without_changing_block_state(self):
        self._inbound('HELP')
        self.assertFalse(self.partner.sms_blocked)
        self.signalwire_client.compat_post.assert_called_once_with(
            'Accounts/sub-abc/Messages.json',
            From='+12084449665', To='+15556102107',
            Body=self.number.sms_help_reply_text)

    def test_an_unrelated_reply_sends_nothing_and_does_not_block(self):
        self._inbound('thanks!')
        self.assertFalse(self.partner.sms_blocked)
        self.signalwire_client.compat_post.assert_not_called()

    def test_stop_reply_failure_still_blocks_the_partner(self):
        from odoo.addons.signalwire_voip.models.signalwire_api import SignalWireAPIError
        self.signalwire_client.compat_post.side_effect = SignalWireAPIError('network down')
        self._inbound('STOP')
        self.assertTrue(self.partner.sms_blocked)


@tagged('post_install', '-at_install')
class TestSendSmsRefusesBlockedPartner(HttpCase):

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
            'name': 'Jane Customer', 'phone': '+15556102107', 'sms_blocked': True,
        })

    def setUp(self):
        super().setUp()
        self.signalwire_client = MagicMock()
        patcher = patch(
            'odoo.addons.signalwire_voip.models.signalwire_server.'
            'SignalWireServer._get_client', return_value=self.signalwire_client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_send_sms_raises_for_a_blocked_partner(self):
        from odoo.exceptions import UserError
        with self.assertRaises(UserError):
            self.number.send_sms('+15556102107', 'hello there')
        self.signalwire_client.compat_post.assert_not_called()

    def test_send_sms_still_works_for_an_unblocked_partner(self):
        self.partner.sms_blocked = False
        self.signalwire_client.compat_post.return_value = {'sid': 'sms-1', 'status': 'queued'}
        self.number.send_sms('+15556102107', 'hello there')
        self.signalwire_client.compat_post.assert_called_once()

    def test_send_sms_works_for_an_unmatched_number(self):
        self.signalwire_client.compat_post.return_value = {'sid': 'sms-1', 'status': 'queued'}
        self.number.send_sms('+19995550000', 'hello there')
        self.signalwire_client.compat_post.assert_called_once()
