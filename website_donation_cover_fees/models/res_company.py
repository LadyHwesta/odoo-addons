# -*- coding: utf-8 -*-
import math

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    donation_cover_fees = fields.Boolean(
        string="Donors Can Cover the Fees", default=True,
        help="Show an unticked \"I'll cover the processing fees\" box on the donation form.")
    donation_fee_percent = fields.Float(
        string="Processing Fee (%)", default=2.9, digits=(5, 3),
        help="The card processor's percentage per payment (Stripe's standard US card rate is "
             "2.9%).")
    donation_fee_fixed = fields.Monetary(
        string="Processing Fee (fixed)", default=0.30, currency_field='currency_id',
        help="The card processor's fixed amount per payment (Stripe's standard US card rate is "
             "0.30).")

    def _donation_cover_fee_rates(self):
        """(percent, fixed) to gross a gift up by. Other modules add their own
        percentage (e.g. a platform's fee) by extending this."""
        self.ensure_one()
        return self.donation_fee_percent or 0.0, self.donation_fee_fixed or 0.0

    def _donation_cover_fee_amount(self, gift, currency=None):
        """What the donor adds to `gift` so that, once the fees are taken from
        the whole payment, `gift` is left: (gift + fixed) / (1 - percent).
        Rounded up to the currency's smallest unit, so the gift is never short.
        """
        self.ensure_one()
        currency = currency or self.currency_id
        percent, fixed = self._donation_cover_fee_rates()
        if gift <= 0 or percent >= 100:
            return 0.0
        total = (gift + fixed) / (1 - percent / 100.0)
        step = currency.rounding or 0.01
        total = math.ceil(round(total / step, 6)) * step
        return currency.round(total - gift)
