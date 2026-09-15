# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSignalWirePhoneNumber10DLC(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'project_id': 'pid123', 'api_token': 'tok456',
        })
        cls.partner = cls.env['res.partner'].create({'name': 'Example Nonprofit'})
        cls.subproject = cls.env['signalwire.subproject'].create({
            'name': 'Example Nonprofit VoIP', 'server_id': cls.server.id,
            'account_sid': 'sub-abc', 'state': 'active', 'partner_id': cls.partner.id,
        })
        cls.number = cls.env['signalwire.phone_number'].create({
            'name': '+14155550100', 'sid': 'pn-123', 'subproject_id': cls.subproject.id,
        })

    def _mock_client(self):
        mock_client = MagicMock()
        patcher = patch(
            'odoo.addons.signalwire_voip.models.signalwire_server.'
            'SignalWireServer._get_client', return_value=mock_client)
        patcher.start()
        self.addCleanup(patcher.stop)
        return mock_client

    def _submitted_campaign(self, mock_client, state='submitted'):
        brand = self.env['signalwire.brand'].create({
            'partner_id': self.partner.id, 'server_id': self.server.id,
            'name': 'Example Nonprofit', 'company_name': 'Example Nonprofit Inc.',
            'contact_email': 'owner@example.org', 'contact_phone': '+15551234567',
            'legal_entity_type': 'PRIVATE_PROFIT', 'ein': '12-3456789',
            'company_address': '123 Main St', 'company_website': 'https://example.org',
            'company_vertical': 'TECHNOLOGY',
        })
        mock_client.registry_post.return_value = {'id': 'brand-abc', 'state': 'submitted'}
        brand.action_submit()
        campaign = self.env['signalwire.campaign'].create({
            'brand_id': brand.id, 'name': 'Support', 'sms_use_case': 'CUSTOMER_CARE',
            'description': 'd', 'message_flow': 'f', 'sample1': 's',
            'opt_in_message': 'in', 'opt_out_message': 'out', 'help_message': 'help',
        })
        mock_client.registry_post.return_value = {'id': 'camp-1', 'state': state}
        campaign.action_submit()
        mock_client.reset_mock()
        return campaign

    def test_enable_without_any_campaign_raises(self):
        with self.assertRaises(UserError):
            self.number.action_request_sms_enablement()

    def test_enable_creates_the_order_and_sets_pending(self):
        mock_client = self._mock_client()
        campaign = self._submitted_campaign(mock_client)

        self.number.action_request_sms_enablement()

        mock_client.registry_post.assert_called_once_with(
            'campaigns/camp-1/orders', phone_numbers=[{'sid': 'pn-123'}])
        self.assertEqual(self.number.campaign_id, campaign)
        self.assertEqual(self.number.campaign_assignment_state, 'pending')

    def test_enable_twice_raises(self):
        mock_client = self._mock_client()
        self._submitted_campaign(mock_client)
        self.number.action_request_sms_enablement()

        with self.assertRaises(UserError):
            self.number.action_request_sms_enablement()

    def test_cron_updates_assignment_state_for_this_number(self):
        mock_client = self._mock_client()
        self._submitted_campaign(mock_client)
        self.number.action_request_sms_enablement()
        mock_client.registry_get.return_value = {
            'data': [{'phone_number': {'id': 'pn-123'}, 'state': 'approved'}]}

        self.env['signalwire.phone_number']._cron_check_campaign_assignment_status()

        self.assertEqual(self.number.campaign_assignment_state, 'approved')

    def test_cron_ignores_entries_for_other_numbers(self):
        mock_client = self._mock_client()
        self._submitted_campaign(mock_client)
        self.number.action_request_sms_enablement()
        mock_client.registry_get.return_value = {
            'data': [{'phone_number': {'id': 'pn-other'}, 'state': 'approved'}]}

        self.env['signalwire.phone_number']._cron_check_campaign_assignment_status()

        self.assertEqual(self.number.campaign_assignment_state, 'pending', "unchanged")
