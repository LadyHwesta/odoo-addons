# -*- coding: utf-8 -*-
from odoo import fields, models


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    donation_gift_amount = fields.Monetary(
        string="Gift", readonly=True,
        help="The gift the donor chose, before any processing fees they covered.")
    donation_fee_covered = fields.Monetary(
        string="Fees Covered by Donor", readonly=True,
        help="What the donor added so the full gift arrives after processing fees.")
