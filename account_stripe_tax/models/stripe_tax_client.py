# -*- coding: utf-8 -*-
"""A small client for Stripe's Tax API, using the Stripe payment provider's key.

Odoo's own Stripe module pins an API version from 2019, before Stripe Tax
existed, so these calls go out without a Stripe-Version header and use the
account's default version instead.
"""
import logging

import requests

from odoo import _
from odoo.exceptions import UserError
from odoo.addons.payment_stripe import utils as stripe_utils

_logger = logging.getLogger(__name__)

API_URL = 'https://api.stripe.com/v1/'
TIMEOUT = 20


def flatten(data, prefix=''):
    """Turn nested dicts/lists into Stripe's form keys: a[b][0][c]=..."""
    items = {}
    if isinstance(data, dict):
        for key, value in data.items():
            items.update(flatten(value, f'{prefix}[{key}]' if prefix else key))
    elif isinstance(data, (list, tuple)):
        for index, value in enumerate(data):
            items.update(flatten(value, f'{prefix}[{index}]'))
    elif data is not None:
        items[prefix] = 'true' if data is True else 'false' if data is False else data
    return items


class StripeTaxClient:

    def __init__(self, provider):
        self.provider = provider.sudo()

    def post(self, endpoint, data, idempotency_key=None):
        headers = {'Authorization': f'Bearer {stripe_utils.get_secret_key(self.provider)}'}
        if idempotency_key:
            headers['Idempotency-Key'] = idempotency_key
        try:
            response = requests.post(
                API_URL + endpoint, data=flatten(data), headers=headers, timeout=TIMEOUT)
        except requests.exceptions.RequestException as exc:
            raise UserError(_("Couldn't reach Stripe Tax: %(error)s", error=exc)) from exc
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        if response.status_code >= 400:
            message = (payload.get('error') or {}).get('message') or response.text[:300]
            _logger.warning("Stripe Tax %s failed (%s): %s", endpoint, response.status_code, message)
            raise UserError(_("Stripe Tax: %(message)s", message=message))
        return payload
