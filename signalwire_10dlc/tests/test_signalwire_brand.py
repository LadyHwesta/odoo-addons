# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSignalWireBrand(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'project_id': 'pid123', 'api_token': 'tok456',
        })
        cls.partner = cls.env['res.partner'].create({'name': 'Example Nonprofit'})

    def _mock_client(self):
        mock_client = MagicMock()
        patcher = patch(
            'odoo.addons.signalwire_voip.models.signalwire_server.'
            'SignalWireServer._get_client', return_value=mock_client)
        patcher.start()
        self.addCleanup(patcher.stop)
        return mock_client

    def _brand(self, **extra):
        vals = {
            'partner_id': self.partner.id, 'server_id': self.server.id,
            'name': 'Example Nonprofit', 'company_name': 'Example Nonprofit Inc.',
            'contact_email': 'owner@example.org', 'contact_phone': '+15551234567',
            'legal_entity_type': 'PRIVATE_PROFIT', 'ein': '12-3456789',
            'company_address': '123 Main St, Springfield, IL', 'company_website': 'https://example.org',
            'company_vertical': 'TECHNOLOGY',
        }
        vals.update(extra)
        return self.env['signalwire.brand'].create(vals)

    def test_submit_calls_registry_post_with_full_payload(self):
        mock_client = self._mock_client()
        mock_client.registry_post.return_value = {'id': 'brand-abc', 'state': 'submitted'}
        brand = self._brand()

        brand.action_submit()

        mock_client.registry_post.assert_called_once()
        args, kwargs = mock_client.registry_post.call_args
        self.assertEqual(args[0], 'brands')
        self.assertEqual(kwargs['ein'], '12-3456789')
        self.assertEqual(kwargs['legal_entity_type'], 'PRIVATE_PROFIT')
        self.assertEqual(brand.signalwire_brand_id, 'brand-abc')
        self.assertEqual(brand.state, 'submitted')

    def test_csp_self_registered_sends_the_short_payload(self):
        mock_client = self._mock_client()
        mock_client.registry_post.return_value = {'id': 'brand-xyz', 'state': 'approved'}
        brand = self._brand(csp_self_registered=True, csp_brand_reference='TCR-EXISTING-123')

        brand.action_submit()

        args, kwargs = mock_client.registry_post.call_args
        self.assertEqual(kwargs, {
            'csp_self_registered': True, 'name': 'Example Nonprofit',
            'csp_brand_reference': 'TCR-EXISTING-123',
        })

    def test_csp_self_registered_without_a_reference_raises(self):
        brand = self._brand(csp_self_registered=True, csp_brand_reference=False)
        with self.assertRaises(UserError):
            brand.action_submit()

    def test_submitting_twice_raises(self):
        mock_client = self._mock_client()
        mock_client.registry_post.return_value = {'id': 'brand-abc', 'state': 'submitted'}
        brand = self._brand()
        brand.action_submit()

        with self.assertRaises(UserError):
            brand.action_submit()

    def test_charges_a_one_time_fee_when_a_priced_product_exists(self):
        self._mock_client().registry_post.return_value = {'id': 'b1', 'state': 'submitted'}
        product = self.env.ref('signalwire_10dlc.product_signalwire_brand_fee')
        product.list_price = 50.0
        brand = self._brand()

        brand.action_submit()

        invoice = self.env['account.move'].search([
            ('partner_id', '=', self.partner.id), ('move_type', '=', 'out_invoice')])
        self.assertEqual(len(invoice), 1)
        self.assertEqual(invoice.invoice_line_ids.price_unit, 50.0)

    def test_no_fee_charged_when_the_product_price_is_zero(self):
        self._mock_client().registry_post.return_value = {'id': 'b1', 'state': 'submitted'}
        brand = self._brand()

        brand.action_submit()

        self.assertFalse(self.env['account.move'].search(
            [('partner_id', '=', self.partner.id), ('move_type', '=', 'out_invoice')]))

    def test_cron_updates_state_from_the_real_api(self):
        mock_client = self._mock_client()
        mock_client.registry_post.return_value = {'id': 'brand-abc', 'state': 'submitted'}
        brand = self._brand()
        brand.action_submit()
        mock_client.registry_get.return_value = {'id': 'brand-abc', 'state': 'approved'}

        self.env['signalwire.brand']._cron_check_brand_status()

        self.assertEqual(brand.state, 'approved')

    def test_cron_survives_one_brand_erroring(self):
        mock_client = self._mock_client()
        mock_client.registry_post.return_value = {'id': 'brand-1', 'state': 'submitted'}
        brand1 = self._brand()
        brand1.action_submit()
        mock_client.registry_post.return_value = {'id': 'brand-2', 'state': 'submitted'}
        brand2 = self._brand(partner_id=self.env['res.partner'].create({'name': 'Other'}).id)
        brand2.action_submit()

        def flaky_get(path):
            if brand1.signalwire_brand_id in path:
                raise Exception("simulated network failure")
            return {'id': brand2.signalwire_brand_id, 'state': 'approved'}
        mock_client.registry_get.side_effect = flaky_get

        self.env['signalwire.brand']._cron_check_brand_status()  # should not raise

        self.assertEqual(brand1.state, 'submitted', "unaffected by its own failed check")
        self.assertEqual(brand2.state, 'approved', "still processed despite brand1's failure")
