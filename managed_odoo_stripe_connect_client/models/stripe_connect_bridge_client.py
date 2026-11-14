# -*- coding: utf-8 -*-
"""A thin client for Meskis' own Stripe Connect bridge - same shape as
every other API client in this project (SignalWireClient, UpCloudClient,
HestiaCPClient): one class, a handful of methods, errors normalized
into one exception type. This instance never holds Meskis' own Stripe
Platform secret - only its own bearer token, scoped to exactly this
instance's own connected account (see managed_odoo_stripe_connect's
own module docstring, in the other repo, for why that split is
structurally required, not just a security nicety).
"""
import logging

import requests

_logger = logging.getLogger(__name__)


class StripeConnectBridgeError(Exception):
    """Raised for any failure calling Meskis' own bridge - a non-2xx
    response, a network error, or an unparseable response.
    """


class StripeConnectBridgeClient:

    def __init__(self, bridge_url, bridge_token, timeout=30):
        self.bridge_url = bridge_url.rstrip('/')
        self.bridge_token = bridge_token
        self.timeout = timeout

    def _post(self, path, json_body):
        try:
            response = requests.post(
                f'{self.bridge_url}/{path}',
                headers={'Authorization': f'Bearer {self.bridge_token}'},
                json=json_body, timeout=self.timeout)
        except requests.RequestException as exc:
            raise StripeConnectBridgeError(
                f"Could not reach Meskis' Stripe Connect bridge: {exc}") from exc
        try:
            body = response.json()
        except ValueError:
            body = {}
        if response.status_code >= 400:
            raise StripeConnectBridgeError(
                body.get('error') or f'Bridge error {response.status_code}')
        return body

    def create_onboarding_link(self):
        """Returns a fresh Stripe-hosted onboarding URL - redirect the
        user there directly, the entire Standard-account signup/KYC
        flow happens on Stripe's own pages.
        """
        return self._post('stripe_connect_bridge/onboarding_link', {})['url']

    def create_payment_intent(self, amount_minor_units, currency, reference):
        """Charges a customer through Meskis' own Platform, with
        Meskis' own cut applied automatically - the amount here is in
        the currency's own minor units (cents for USD), matching
        Stripe's own convention.
        """
        return self._post('stripe_connect_bridge/charge', {
            'amount': amount_minor_units, 'currency': currency, 'reference': reference,
        })
