# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    support_mobile = fields.Char(
        string='Mobile for Support Codes',
        help="The mobile number support verification codes are texted to. "
             "Empty: the contact's phone number is used.")
