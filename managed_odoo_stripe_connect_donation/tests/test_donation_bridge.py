# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.payment_stripe.tests.common import StripeCommon

CLIENT = ('odoo.addons.managed_odoo_stripe_connect_client.models.stripe_connect_bridge_client.'
          'StripeConnectBridgeClient')


@tagged('post_install', '-at_install')
class TestDonorCoveredFeesThroughMeskis(StripeCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.provider.company_id
        cls.company.write({
            'stripe_connect_bridge_url': 'https://meskis.net',
            'stripe_connect_bridge_token': 'tok-abc123',
            'donation_fee_percent': 2.9, 'donation_fee_fixed': 0.30,
        })
        with patch(f'{CLIENT}.checkout_config', return_value={
                'publishable_key': 'pk_test_x', 'stripe_account_id': 'acct_np1',
                'webhook_secret': 'whsec_' + 'test' * 8, 'application_fee_percent': 1.0}):
            cls.provider.action_stripe_connect_use_bridge()
        cls.provider.state = 'enabled'

    def test_the_fee_percent_comes_from_the_bridge(self):
        self.assertEqual(self.company.stripe_connect_fee_percent, 1.0)

    def test_covering_the_fees_includes_meskis_fee(self):
        self.assertEqual(self.company._donation_cover_fee_rates(), (3.9, 0.30))
        # (25 + 0.30) / (1 - 0.039) = 26.3267... -> 26.33
        self.assertAlmostEqual(
            self.company._donation_cover_fee_amount(25.0, self.currency), 1.33)

    def test_without_payments_through_meskis_only_the_processor_fee(self):
        self.provider.state = 'disabled'
        self.assertEqual(self.company._donation_cover_fee_rates(), (2.9, 0.30))

    def test_a_fee_covered_donation_is_marked_for_the_bridge(self):
        tx = self._create_transaction('direct', amount=26.33)
        tx.write({'donation_gift_amount': 25.0, 'donation_fee_covered': 1.33})
        with patch(f'{CLIENT}.relay', return_value=(200, {'id': 'cus_1'})):
            payload = tx._stripe_prepare_payment_intent_payload()
        self.assertEqual(payload['metadata[meskis_fee_covered]'], '1')
        self.assertEqual(payload['metadata[gift_amount]'], 2500)

    def test_an_ordinary_payment_is_not_marked(self):
        tx = self._create_transaction('direct')
        with patch(f'{CLIENT}.relay', return_value=(200, {'id': 'cus_1'})):
            payload = tx._stripe_prepare_payment_intent_payload()
        self.assertNotIn('metadata[meskis_fee_covered]', payload)

    def test_the_daily_refresh_picks_up_a_new_fee(self):
        with patch(f'{CLIENT}.checkout_config', return_value={'application_fee_percent': 1.5}):
            self.env['res.company']._cron_stripe_connect_refresh_fee()
        self.assertEqual(self.company.stripe_connect_fee_percent, 1.5)
