# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    imaps = fields.One2many(
        'res.company.imap', 'company', string='IMAP Authentication Servers',
        copy=True, groups='base.group_system')
