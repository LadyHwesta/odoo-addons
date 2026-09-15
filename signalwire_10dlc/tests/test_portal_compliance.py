# -*- coding: utf-8 -*-
import re
from unittest.mock import MagicMock, patch

from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestPortalCompliance(HttpCase):

    def setUp(self):
        super().setUp()
        self.mock_client = MagicMock()
        patcher = patch(
            'odoo.addons.signalwire_voip.models.signalwire_server.'
            'SignalWireServer._get_client', return_value=self.mock_client)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.server = self.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'project_id': 'pid123', 'api_token': 'tok456',
        })
        self.owner = self._portal_user('owner_10dlc')
        self.other = self._portal_user('other_10dlc')
        self.subproject = self.env['signalwire.subproject'].create({
            'name': 'Sub', 'server_id': self.server.id, 'account_sid': 'sub-abc',
            'state': 'active', 'partner_id': self.owner.partner_id.id,
        })
        self.number = self.env['signalwire.phone_number'].create({
            'name': '+14155550100', 'sid': 'pn-123', 'subproject_id': self.subproject.id,
        })

    def _portal_user(self, login):
        return self.env['res.users'].create({
            'name': login, 'login': login, 'password': login,
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])],
        })

    def _csrf_token(self):
        page = self.url_open('/my/sms/compliance')
        match = re.search(r'name="csrf_token" value="([^"]+)"', page.text)
        self.assertTrue(match, "no csrf_token found on /my/sms/compliance")
        return match.group(1)

    def _compliance_form_data(self, csrf_token):
        return {
            'csrf_token': csrf_token,
            'name': 'My Business', 'company_name': 'My Business Inc.',
            'contact_email': 'me@example.org', 'contact_phone': '+15551234567',
            'ein': '12-3456789', 'ein_issuing_country': 'US',
            'legal_entity_type': 'PRIVATE_PROFIT', 'company_website': 'https://example.org',
            'company_vertical': 'TECHNOLOGY', 'company_address': '123 Main St',
            'campaign_name': 'Support', 'sms_use_case': 'CUSTOMER_CARE',
            'description': 'Customer support', 'message_flow': 'They text us',
            'sample1': 'Thanks for reaching out!', 'opt_in_message': 'in',
            'opt_out_message': 'out', 'help_message': 'help',
        }

    # -- ownership --------------------------------------------------------

    def test_other_user_cannot_see_owners_brand(self):
        self.mock_client.registry_post.return_value = {'id': 'brand-1', 'state': 'submitted'}
        brand = self.env['signalwire.brand'].create({
            'partner_id': self.owner.partner_id.id, 'server_id': self.server.id,
            'name': 'X', 'company_name': 'X Inc.', 'contact_email': 'x@example.org',
            'contact_phone': '+15551234567', 'legal_entity_type': 'PRIVATE_PROFIT',
            'ein': '1', 'company_address': 'a', 'company_website': 'https://x.example.org',
            'company_vertical': 'TECHNOLOGY',
        })
        self.authenticate('other_10dlc', 'other_10dlc')
        found = self.env['signalwire.brand'].with_user(self.other).search(
            [('id', '=', brand.id)])
        self.assertFalse(found)

    def test_other_user_cannot_enable_sms_on_owners_number(self):
        self.mock_client.registry_post.return_value = {'id': 'brand-1', 'state': 'submitted'}
        brand = self.env['signalwire.brand'].create({
            'partner_id': self.owner.partner_id.id, 'server_id': self.server.id,
            'name': 'X', 'company_name': 'X Inc.', 'contact_email': 'x@example.org',
            'contact_phone': '+15551234567', 'legal_entity_type': 'PRIVATE_PROFIT',
            'ein': '1', 'company_address': 'a', 'company_website': 'https://x.example.org',
            'company_vertical': 'TECHNOLOGY',
        })
        brand.action_submit()
        campaign = self.env['signalwire.campaign'].create({
            'brand_id': brand.id, 'name': 'C', 'sms_use_case': 'CUSTOMER_CARE',
            'description': 'd', 'message_flow': 'f', 'sample1': 's',
            'opt_in_message': 'in', 'opt_out_message': 'out', 'help_message': 'help',
        })
        self.mock_client.registry_post.return_value = {'id': 'camp-1', 'state': 'submitted'}
        campaign.action_submit()

        self.authenticate('other_10dlc', 'other_10dlc')
        self.url_open(f'/my/sms/{self.number.id}/enable_sms', data={'csrf_token': 'x'})

        self.assertFalse(self.number.campaign_id, "not this user's number - must not be touched")

    # -- the owner's own flow works -----------------------------------------

    def test_owner_can_submit_the_compliance_form(self):
        self.mock_client.registry_post.side_effect = [
            {'id': 'brand-1', 'state': 'submitted'},
            {'id': 'camp-1', 'state': 'submitted'},
        ]
        self.authenticate('owner_10dlc', 'owner_10dlc')
        csrf_token = self._csrf_token()

        self.url_open('/my/sms/compliance', data=self._compliance_form_data(csrf_token))

        brand = self.env['signalwire.brand'].search(
            [('partner_id', '=', self.owner.partner_id.id)])
        self.assertEqual(len(brand), 1)
        self.assertEqual(brand.state, 'submitted')
        campaign = self.env['signalwire.campaign'].search([('brand_id', '=', brand.id)])
        self.assertEqual(len(campaign), 1)

    def test_owner_can_enable_sms_once_they_have_a_campaign(self):
        self.mock_client.registry_post.side_effect = [
            {'id': 'brand-1', 'state': 'submitted'},
            {'id': 'camp-1', 'state': 'submitted'},
        ]
        self.authenticate('owner_10dlc', 'owner_10dlc')
        csrf_token = self._csrf_token()
        self.url_open('/my/sms/compliance', data=self._compliance_form_data(csrf_token))
        self.mock_client.registry_post.side_effect = None
        self.mock_client.registry_post.return_value = {'status': 'ok'}

        self.url_open(f'/my/sms/{self.number.id}/enable_sms', data={'csrf_token': csrf_token})

        self.assertEqual(self.number.campaign_assignment_state, 'pending')

    def test_enabling_sms_without_a_campaign_redirects_to_compliance_form(self):
        self.authenticate('owner_10dlc', 'owner_10dlc')
        csrf_token = self._csrf_token()

        resp = self.url_open(
            f'/my/sms/{self.number.id}/enable_sms', data={'csrf_token': csrf_token})

        self.assertIn('/my/sms/compliance', resp.url)
        self.assertFalse(self.number.campaign_id)
