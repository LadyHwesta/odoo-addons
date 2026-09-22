# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSignalWirePhoneNumberSms(TransactionCase):

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

    def setUp(self):
        super().setUp()
        self.signalwire_client = MagicMock()
        patcher = patch(
            'odoo.addons.signalwire_voip.models.signalwire_server.'
            'SignalWireServer._get_client', return_value=self.signalwire_client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_send_sms_calls_the_messages_endpoint(self):
        self.signalwire_client.compat_post.return_value = {
            'sid': 'sms-1', 'status': 'queued',
        }

        self.number.send_sms('+15556102107', 'hello there')

        self.signalwire_client.compat_post.assert_called_once_with(
            'Accounts/sub-abc/Messages.json',
            From='+12084449665', To='+15556102107', Body='hello there')

    def test_send_sms_creates_a_message_record(self):
        self.signalwire_client.compat_post.return_value = {
            'sid': 'sms-1', 'status': 'queued',
        }

        message = self.number.send_sms('+15556102107', 'hello there')

        self.assertEqual(message.direction, 'outbound')
        self.assertEqual(message.body, 'hello there')
        self.assertEqual(message.sid, 'sms-1')
        self.assertEqual(message.state, 'queued')

    def test_sms_count_reflects_created_messages(self):
        self.signalwire_client.compat_post.return_value = {'sid': 'sms-1', 'status': 'queued'}
        self.number.send_sms('+15556102107', 'one')
        self.number.send_sms('+15556102107', 'two')

        self.assertEqual(self.number.sms_count, 2)

    def test_form_view_extends_rather_than_replaces_the_base_one(self):
        """Regression test: this module's own phone number form view
        used to be a second, independent root view for the same model
        (no inherit_id at all, just a record sharing the base view's
        own name) rather than a real extension - Odoo's default view
        resolution then arbitrarily picked whichever root view was
        installed last, silently dropping every field any other
        module (routing, IVR, call groups, business hours) had added
        to the real base view. Confirmed live: a phone number's own
        form showed only this module's own fields and nothing else.
        Now a proper inherit_id extension - confirm the composed view
        still carries the base view's own fields alongside this
        module's own addition.
        """
        view = self.number.get_view(
            view_id=self.env.ref('signalwire_voip.view_signalwire_phone_number_form').id,
            view_type='form')

        self.assertIn('sms_webhook_url', view['arch'])
        self.assertIn('sid', view['arch'])
