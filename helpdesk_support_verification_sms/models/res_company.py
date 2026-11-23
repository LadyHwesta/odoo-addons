# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    support_sms_number_id = fields.Many2one(
        'signalwire.phone_number', string='Text Support Codes From',
        domain="[('company_id', 'in', (id, False))]",
        help="Our number that sends support verification codes. It must be "
             "registered for business texting.")


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    support_sms_number_id = fields.Many2one(
        related='company_id.support_sms_number_id', readonly=False)
