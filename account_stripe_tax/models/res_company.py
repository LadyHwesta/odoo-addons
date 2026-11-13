# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    stripe_tax_provider_id = fields.Many2one(
        'payment.provider', string="Stripe Tax Account",
        domain="[('code', '=', 'stripe'), ('company_id', '=', id)]",
        help="The Stripe payment provider whose API key is used for Stripe Tax. "
             "Empty: Stripe Tax is off.")
    stripe_tax_account_id = fields.Many2one(
        'account.account', string="Sales Tax Account",
        help="Where the sales tax Stripe Tax works out is posted (your sales "
             "tax payable account).")
    stripe_tax_record_all = fields.Boolean(
        string="Record Untaxed Sales in Stripe",
        help="Also record invoices with no sales tax (e.g. customers in other "
             "states), so Stripe's threshold monitoring sees every sale. "
             "Stripe charges per recorded sale where you're registered, so "
             "this costs more; off, only taxed sales are recorded.")
