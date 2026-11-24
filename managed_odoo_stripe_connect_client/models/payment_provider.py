# -*- coding: utf-8 -*-
"""Core payment_stripe checkout, through Meskis' bridge.

With "Payments through Meskis" switched on, this Stripe provider holds no
Stripe secret key of its own. Every Stripe call core payment_stripe makes
(customers, payment and setup intents, saved cards, capture, refunds,
Apple Pay) goes to the bridge, which makes it with the platform's key on
this instance's own Stripe account and adds Meskis' fee. The card form
loads Stripe.js with the platform's publishable key and this account's id
(Stripe's documented way to take direct charges for a connected account).
Stripe's payment updates reach this Odoo's normal Stripe webhook, passed on
by the bridge and signed with a secret only this instance and the bridge
share.

Everything else in payment_stripe (the checkout pages, saved cards, the
payment status page, refunds from invoices) is core's own code, unchanged.
"""
from odoo import _, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.payment_stripe import const

from .stripe_connect_bridge_client import StripeConnectBridgeError


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    stripe_connect_bridged = fields.Boolean(
        string="Payments through Meskis", copy=False,
        help="Card payments run on your own Stripe account through Meskis' platform: no "
             "Stripe keys to enter here.")

    # -- switching it on and off --------------------------------------------------

    def action_stripe_connect_use_bridge(self):
        self.ensure_one()
        if self.code != 'stripe':
            raise UserError(_("Only the Stripe provider can take payments through Meskis."))
        config = self.company_id._get_stripe_connect_bridge_client().checkout_config()
        self.company_id.stripe_connect_account_id = config['stripe_account_id']
        vals = {}
        if self.state == 'test':
            # Live or test is the bridge's to decide; never switch a test
            # provider straight to live: it waits, disabled, to be enabled.
            vals['state'] = 'disabled'
        self.write({
            **vals,
            'stripe_connect_bridged': True,
            'stripe_publishable_key': config['publishable_key'],
            'stripe_secret_key': False,
            'stripe_webhook_secret': config['webhook_secret'],
        })

    def action_stripe_connect_stop_bridge(self):
        self.ensure_one()
        self.write({
            'stripe_connect_bridged': False,
            'state': 'disabled',
            'stripe_publishable_key': False,
            'stripe_webhook_secret': False,
        })

    # -- payment_stripe's Stripe Connect hooks ---------------------------------

    def _stripe_has_connected_account(self):
        """Override of payment_stripe: test mode makes no sense here, since the
        platform's key decides live or test."""
        self.ensure_one()
        return self.stripe_connect_bridged or super()._stripe_has_connected_account()

    def _stripe_connect_account_for_js(self):
        """The account id Stripe.js must load with, or '' when not bridged."""
        self.ensure_one()
        if not self.stripe_connect_bridged:
            return ''
        return self.sudo().company_id.stripe_connect_account_id or ''

    def _check_required_if_provider(self):
        """Override of payment: a bridged provider has no secret key of its own."""
        bridged = self.filtered(lambda p: p.code == 'stripe' and p.stripe_connect_bridged)
        super(PaymentProvider, self - bridged)._check_required_if_provider()
        for provider in bridged.filtered(lambda p: p.state in ('enabled', 'test')):
            if not provider.stripe_publishable_key:
                raise ValidationError(_(
                    "Use \"Take payments through Meskis\" to fill in this provider first."))

    def _send_api_request(
        self, method, endpoint, *, params=None, data=None, json=None, reference=None, **kwargs
    ):
        """Override of payment: send a bridged provider's Stripe calls to the bridge."""
        if self.code != 'stripe' or not self.stripe_connect_bridged:
            return super()._send_api_request(
                method, endpoint, params=params, data=data, json=json, reference=reference,
                **kwargs)
        self.ensure_one()
        if kwargs.get('is_proxy_request'):
            raise UserError(_(
                "Stripe's own Connect onboarding isn't used with payments through Meskis."))
        if endpoint == 'webhook_endpoints':
            raise UserError(_(
                "Payment updates already reach this Odoo through Meskis: no webhook to set up."))
        payload = params or data or json or {}
        self._log_request(method, f'bridge:{endpoint}', payload, reference=reference)
        try:
            status, body = self.company_id.sudo()._get_stripe_connect_bridge_client().relay(
                method, endpoint, data=payload, stripe_version=const.API_VERSION,
                idempotency_key=kwargs.get('idempotency_key'))
        except StripeConnectBridgeError as exc:
            raise ValidationError(_(
                "Could not establish the connection to the payment provider.\n%s", exc))
        if status >= 400:
            error = body.get('error')
            message = error.get('message') if isinstance(error, dict) else error
            raise ValidationError(_(
                "The payment provider rejected the request.\n%s", message or status))
        return body
