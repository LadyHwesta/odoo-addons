# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

from odoo.addons.website_payment.controllers.portal import PaymentPortal


class CoverFeesPaymentPortal(PaymentPortal):

    @http.route()
    def donation_transaction(self, amount, currency_id, partner_id, access_token,
                             minimum_amount=0, **kwargs):
        """The donor ticked "cover the fees": add them here, on the server, from
        the gift they chose. The figure shown in the browser is only a preview."""
        cover_fees = bool(kwargs.pop('donation_cover_fees', False))
        company = request.website.company_id
        gift = float(amount)
        covered = 0.0
        if cover_fees and company.donation_cover_fees:
            currency = request.env['res.currency'].browse(int(currency_id or 0)).exists() \
                or company.currency_id
            covered = company._donation_cover_fee_amount(gift, currency)
        # Set on the transaction when it's created (see _create_transaction):
        # the payment provider may already act on it in the same request.
        request.update_context(donation_cover_values={
            'donation_gift_amount': gift, 'donation_fee_covered': covered})
        return super().donation_transaction(
            gift + covered, currency_id, partner_id, access_token,
            minimum_amount=minimum_amount, **kwargs)

    def _create_transaction(self, *args, custom_create_values=None, **kwargs):
        cover_values = request.env.context.get('donation_cover_values')
        if cover_values:
            custom_create_values = {**(custom_create_values or {}), **cover_values}
        return super()._create_transaction(
            *args, custom_create_values=custom_create_values, **kwargs)
