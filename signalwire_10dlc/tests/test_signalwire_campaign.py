# -*- coding: utf-8 -*-
from datetime import date
from unittest.mock import MagicMock, patch

from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSignalWireCampaign(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'project_id': 'pid123', 'api_token': 'tok456',
        })
        cls.partner = cls.env['res.partner'].create({'name': 'Example Nonprofit'})
        cls.brand = cls.env['signalwire.brand'].create({
            'partner_id': cls.partner.id, 'server_id': cls.server.id,
            'name': 'Example Nonprofit', 'company_name': 'Example Nonprofit Inc.',
            'contact_email': 'owner@example.org', 'contact_phone': '+15551234567',
            'legal_entity_type': 'PRIVATE_PROFIT', 'ein': '12-3456789',
            'company_address': '123 Main St', 'company_website': 'https://example.org',
            'company_vertical': 'TECHNOLOGY',
        })

    def _mock_client(self):
        mock_client = MagicMock()
        patcher = patch(
            'odoo.addons.signalwire_voip.models.signalwire_server.'
            'SignalWireServer._get_client', return_value=mock_client)
        patcher.start()
        self.addCleanup(patcher.stop)
        return mock_client

    def _submitted_brand(self, mock_client):
        mock_client.registry_post.return_value = {'id': 'brand-abc', 'state': 'submitted'}
        self.brand.action_submit()
        mock_client.reset_mock()

    def _campaign(self, **extra):
        vals = {
            'brand_id': self.brand.id, 'name': 'Support Campaign',
            'sms_use_case': 'CUSTOMER_CARE', 'description': 'Customer support texts',
            'message_flow': 'Customer texts our support line',
            'sample1': 'Thanks for contacting support!',
            'opt_in_message': 'You are opted in.', 'opt_out_message': 'You are opted out.',
            'help_message': 'Reply HELP for help.',
        }
        vals.update(extra)
        return self.env['signalwire.campaign'].create(vals)

    def test_submit_requires_the_brand_to_already_be_submitted(self):
        campaign = self._campaign()
        with self.assertRaises(UserError):
            campaign.action_submit()

    def test_submit_calls_registry_post_nested_under_the_brand(self):
        mock_client = self._mock_client()
        self._submitted_brand(mock_client)
        mock_client.registry_post.return_value = {'id': 'camp-1', 'state': 'submitted'}
        campaign = self._campaign()

        campaign.action_submit()

        args, kwargs = mock_client.registry_post.call_args
        self.assertEqual(args[0], 'brands/brand-abc/campaigns')
        self.assertEqual(kwargs['sms_use_case'], 'CUSTOMER_CARE')
        self.assertEqual(campaign.signalwire_campaign_id, 'camp-1')
        self.assertEqual(campaign.state, 'submitted')

    def test_submit_sets_the_three_month_minimum_commitment(self):
        mock_client = self._mock_client()
        self._submitted_brand(mock_client)
        mock_client.registry_post.return_value = {'id': 'camp-1', 'state': 'submitted'}
        campaign = self._campaign()

        campaign.action_submit()

        self.assertEqual(
            campaign.min_commitment_end_date, date.today() + relativedelta(months=3))

    def test_submit_starts_billing_when_a_priced_product_exists(self):
        mock_client = self._mock_client()
        self._submitted_brand(mock_client)
        mock_client.registry_post.return_value = {'id': 'camp-1', 'state': 'submitted'}
        product = self.env.ref('signalwire_10dlc.product_signalwire_campaign_fee')
        product.list_price = 25.0
        campaign = self._campaign()

        campaign.action_submit()

        self.assertTrue(campaign.contract_id)
        line = campaign.contract_id.contract_line_ids
        self.assertEqual(line.price_unit, 25.0)
        self.assertEqual(line.recurring_rule_type, 'monthly')

    def test_cancel_before_the_minimum_commitment_raises(self):
        mock_client = self._mock_client()
        self._submitted_brand(mock_client)
        mock_client.registry_post.return_value = {'id': 'camp-1', 'state': 'submitted'}
        campaign = self._campaign()
        campaign.action_submit()

        with self.assertRaises(UserError):
            campaign.action_cancel()

    def test_cancel_after_the_minimum_commitment_ends_the_line_and_cancels(self):
        mock_client = self._mock_client()
        self._submitted_brand(mock_client)
        mock_client.registry_post.return_value = {'id': 'camp-1', 'state': 'submitted'}
        product = self.env.ref('signalwire_10dlc.product_signalwire_campaign_fee')
        product.list_price = 25.0
        campaign = self._campaign()
        campaign.action_submit()
        campaign.min_commitment_end_date = date.today()  # simulate the 3 months having passed

        campaign.action_cancel()

        self.assertEqual(campaign.state, 'cancelled')
        self.assertEqual(campaign.contract_id.contract_line_ids.date_end, date.today())

    def test_cron_updates_state_from_the_real_api(self):
        mock_client = self._mock_client()
        self._submitted_brand(mock_client)
        mock_client.registry_post.return_value = {'id': 'camp-1', 'state': 'submitted'}
        campaign = self._campaign()
        campaign.action_submit()
        mock_client.registry_get.return_value = {'id': 'camp-1', 'state': 'approved'}

        self.env['signalwire.campaign']._cron_check_campaign_status()

        self.assertEqual(campaign.state, 'approved')
