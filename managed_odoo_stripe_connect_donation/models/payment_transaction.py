# -*- coding: utf-8 -*-
from odoo import models

from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment_stripe import const


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _stripe_prepare_payment_intent_payload(self):
        """Mark a donation whose donor covered the fees, so Meskis' bridge can
        credit its share to this organisation's hosting invoices."""
        payload = super()._stripe_prepare_payment_intent_payload()
        if self.donation_fee_covered and self.provider_id.stripe_connect_bridged:
            payload['metadata[meskis_fee_covered]'] = '1'
            payload['metadata[gift_amount]'] = payment_utils.to_minor_currency_units(
                self.donation_gift_amount, self.currency_id,
                arbitrary_decimal_number=const.CURRENCY_DECIMALS.get(self.currency_id.name))
        return payload
