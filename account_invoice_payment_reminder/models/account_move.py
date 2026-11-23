# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    sent_reminder_stage_ids = fields.Many2many(
        'account.reminder.stage', string="Reminders Sent", readonly=True,
        help="Which reminder stages have already been emailed for this "
             "invoice - each stage only ever fires once per invoice.")
    last_reminder_date = fields.Datetime(readonly=True)
