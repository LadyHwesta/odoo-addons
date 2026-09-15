# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestComposeWizard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'project_id': 'pid123', 'api_token': 'tok456',
        })
        cls.internal_subproject = cls.env['signalwire.subproject'].create({
            'name': 'Internal Team', 'server_id': cls.server.id,
            'account_sid': 'sub-internal', 'state': 'active',
        })
        cls.internal_number = cls.env['signalwire.phone_number'].create({
            'name': '+12084449665', 'sid': 'pn-internal',
            'subproject_id': cls.internal_subproject.id,
        })
        cls.customer_partner = cls.env['res.partner'].create({'name': 'Reseller Customer'})
        cls.customer_subproject = cls.env['signalwire.subproject'].create({
            'name': 'Customer Subproject', 'server_id': cls.server.id,
            'account_sid': 'sub-customer', 'state': 'active',
            'partner_id': cls.customer_partner.id,
        })
        cls.customer_number = cls.env['signalwire.phone_number'].create({
            'name': '+13052808277', 'sid': 'pn-customer',
            'subproject_id': cls.customer_subproject.id,
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'Jane Customer', 'phone': '+15556102107',
        })

    def setUp(self):
        super().setUp()
        self.signalwire_client = MagicMock()
        patcher = patch(
            'odoo.addons.signalwire_voip.models.signalwire_server.'
            'SignalWireServer._get_client', return_value=self.signalwire_client)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.signalwire_client.compat_post.return_value = {'sid': 'sms-1', 'status': 'queued'}

    def test_default_from_number_is_not_a_resold_customer_number(self):
        wizard = self.env['signalwire.sms.compose'].with_context(
            default_partner_id=self.partner.id).create({
                'partner_id': self.partner.id, 'to': '+15556102107', 'body': 'hi',
            })
        self.assertEqual(wizard.phone_number_id, self.internal_number)

    def test_partner_button_opens_the_wizard_prefilled(self):
        action = self.partner.action_open_signalwire_sms_compose()
        self.assertEqual(action['res_model'], 'signalwire.sms.compose')
        self.assertEqual(action['context']['default_partner_id'], self.partner.id)
        self.assertEqual(action['context']['default_to'], '+15556102107')

    def test_send_creates_the_message(self):
        wizard = self.env['signalwire.sms.compose'].create({
            'partner_id': self.partner.id,
            'phone_number_id': self.internal_number.id,
            'to': '+15556102107', 'body': 'hi there',
        })

        wizard.action_send()

        self.signalwire_client.compat_post.assert_called_once_with(
            'Accounts/sub-internal/Messages.json',
            From='+12084449665', To='+15556102107', Body='hi there')
