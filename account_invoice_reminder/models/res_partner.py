# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    reminder_exempt = fields.Boolean(
        string="Exclude from Automatic Payment Reminders",
        help="This contact's overdue invoices are skipped by the "
             "automatic reminder schedule entirely - for board members, "
             "major donors, or any account someone would rather follow "
             "up with personally.")
