# -*- coding: utf-8 -*-
import hashlib
import hmac
import json
import time
from unittest.mock import patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.payment.tests.http_common import PaymentHttpCommon
from odoo.addons.payment_stripe.controllers.main import StripeController
from odoo.addons.payment_stripe.tests.common import StripeCommon

CLIENT = ('odoo.addons.managed_odoo_stripe_connect_client.models.stripe_connect_bridge_client.'
          'StripeConnectBridgeClient')
# A made-up value, built at run time so secret scanners don't mistake the
# source for a real Stripe signing secret (GitHub alert #1, 2026-11-23).
FORWARD_SECRET = 'whsec_' + 'test' * 8


@tagged('post_install', '-at_install')
class TestPaymentsThroughMeskis(StripeCommon, PaymentHttpCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider.company_id.write({
            'stripe_connect_bridge_url': 'https://meskis.net',
            'stripe_connect_bridge_token': 'tok-abc123',
        })

    def _use_bridge(self):
        with patch(f'{CLIENT}.checkout_config', return_value={
                'publishable_key': 'pk_test_platform', 'stripe_account_id': 'acct_cust1',
                'webhook_secret': FORWARD_SECRET}):
            self.provider.action_stripe_connect_use_bridge()

    def test_switching_on_fills_the_provider_and_drops_its_own_secret_key(self):
        self._use_bridge()
        self.assertTrue(self.provider.stripe_connect_bridged)
        self.assertEqual(self.provider.stripe_publishable_key, 'pk_test_platform')
        self.assertFalse(self.provider.stripe_secret_key)
        self.assertEqual(self.provider.stripe_webhook_secret, FORWARD_SECRET)
        self.assertEqual(self.provider.company_id.stripe_connect_account_id, 'acct_cust1')
        self.assertEqual(self.provider._stripe_connect_account_for_js(), 'acct_cust1')
        self.assertEqual(self.provider.state, 'disabled')  # was in test mode: never straight to live

    def test_an_enabled_bridged_provider_needs_no_secret_key(self):
        self._use_bridge()
        self.provider.state = 'enabled'  # would raise if the secret key were still required

    def test_an_ordinary_stripe_provider_still_needs_its_secret_key(self):
        with self.assertRaises(ValidationError):
            self.provider.write({'state': 'enabled', 'stripe_secret_key': False})

    def test_test_mode_is_not_offered_through_the_bridge(self):
        self._use_bridge()
        with self.assertRaises(ValidationError):
            self.provider.state = 'test'

    def test_stripe_calls_go_through_the_bridge(self):
        self._use_bridge()
        with patch(f'{CLIENT}.relay', return_value=(200, {'id': 'cus_1'})) as relay:
            result = self.provider._send_api_request(
                'POST', 'customers', data={'name': 'Norbert'}, idempotency_key='k1')
        self.assertEqual(result, {'id': 'cus_1'})
        args, kwargs = relay.call_args
        self.assertEqual(args, ('POST', 'customers'))
        self.assertEqual(kwargs['data'], {'name': 'Norbert'})
        self.assertEqual(kwargs['stripe_version'], '2019-05-16')
        self.assertEqual(kwargs['idempotency_key'], 'k1')

    def test_a_declined_card_reads_like_stripes_own_error(self):
        self._use_bridge()
        with patch(f'{CLIENT}.relay', return_value=(
                402, {'error': {'message': 'Your card was declined.'}})):
            with self.assertRaises(ValidationError) as cm:
                self.provider._send_api_request('POST', 'payment_intents', data={'amount': 100})
        self.assertIn('Your card was declined.', str(cm.exception))

    def test_a_whole_payment_intent_is_made_through_the_bridge(self):
        self._use_bridge()
        tx = self._create_transaction('direct')
        with patch(f'{CLIENT}.relay', side_effect=[
                (200, {'id': 'cus_1'}),
                (200, {'id': 'pi_1', 'client_secret': 'pi_1_secret_x'})]) as relay:
            intent = tx._stripe_create_intent()
        self.assertEqual(intent['id'], 'pi_1')
        self.assertEqual([c.args[1] for c in relay.call_args_list], ['customers', 'payment_intents'])
        pi_data = relay.call_args_list[1].kwargs['data']
        self.assertEqual(pi_data['customer'], 'cus_1')
        self.assertEqual(pi_data['description'], tx.reference)
        self.assertNotIn('application_fee_amount', pi_data)  # the bridge adds it, not us

    def test_an_ordinary_stripe_provider_is_untouched(self):
        with patch(f'{CLIENT}.relay') as relay, \
                patch('requests.request') as req:
            req.return_value.json.return_value = {'id': 'cus_1'}
            req.return_value.status_code = 200
            self.provider._send_api_request('POST', 'customers', data={})
        relay.assert_not_called()
        self.assertTrue(req.call_args.args[1].startswith('https://api.stripe.com/v1/'))

    def test_stripes_webhook_setup_is_refused_when_bridged(self):
        self._use_bridge()
        self.provider.stripe_webhook_secret = False
        self.provider.stripe_secret_key = 'unused'  # make core's button think it can run
        with self.assertRaises(UserError):
            self.provider.action_stripe_create_webhook()

    def test_the_express_checkout_form_loads_stripe_on_the_customers_account(self):
        self._use_bridge()
        html = self.env['ir.qweb']._render(
            'payment_stripe.express_checkout_form', {'provider_sudo': self.provider.sudo()})
        self.assertIn('data-stripe-account="acct_cust1"', str(html))

    def test_an_ordinary_form_has_no_account_attribute(self):
        html = self.env['ir.qweb']._render(
            'payment_stripe.express_checkout_form', {'provider_sudo': self.provider.sudo()})
        self.assertNotIn('data-stripe-account', str(html))

    def test_a_payment_update_passed_on_by_the_bridge_confirms_the_order(self):
        self._use_bridge()
        tx = self._create_transaction('redirect')
        payload = json.dumps(self.payment_data).encode()
        timestamp = int(time.time())
        signature = hmac.new(
            FORWARD_SECRET.encode(), f'{timestamp}.{payload.decode()}'.encode(),
            hashlib.sha256).hexdigest()
        response = self.url_open(
            self._build_url(StripeController._webhook_url), data=payload,
            headers={'Content-Type': 'application/json',
                     'Stripe-Signature': f't={timestamp},v1={signature}'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(tx.state, 'done')

    def test_switching_off_disables_the_provider(self):
        self._use_bridge()
        self.provider.action_stripe_connect_stop_bridge()
        self.assertFalse(self.provider.stripe_connect_bridged)
        self.assertEqual(self.provider.state, 'disabled')
        self.assertFalse(self.provider.stripe_publishable_key)
