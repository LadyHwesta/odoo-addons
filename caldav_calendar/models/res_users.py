# -*- coding: utf-8 -*-
from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    caldav_account_ids = fields.One2many('caldav.account', 'user_id', string='CalDAV Calendar Accounts')

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['caldav_account_ids']
