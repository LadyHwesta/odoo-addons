# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountReminderStage(models.Model):
    """One touchpoint in a customer invoice's reminder schedule.

    `days_offset` is signed and does double duty as both "how many
    days before/after the due date" and "before or after": negative
    fires before the due date, zero on the due date itself, positive
    after (overdue). See `_cron_send_reminders` for why a before/on
    stage is only ever sent on its exact day while an overdue stage is
    allowed to catch up if the cron run was ever delayed.
    """
    _name = 'account.reminder.stage'
    _description = 'Invoice Reminder Stage'
    _order = 'sequence, days_offset'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    days_offset = fields.Integer(
        required=True,
        help="Days relative to the invoice's due date: negative sends "
             "before it's due, zero on the due date, positive once "
             "it's overdue.")
    mail_template_id = fields.Many2one(
        'mail.template', required=True, string="Email Template",
        domain=[('model', '=', 'account.move')])
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)

    @api.model
    def _cron_send_reminders(self):
        today = fields.Date.context_today(self)
        invoices = self.env['account.move'].search([
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('payment_state', 'not in', ('paid', 'in_payment', 'reversed')),
            ('invoice_date_due', '!=', False),
            ('partner_id.reminder_exempt', '=', False),
        ])
        stages_by_company = {}
        for invoice in invoices:
            company_id = invoice.company_id.id
            if company_id not in stages_by_company:
                stages_by_company[company_id] = self.search([
                    ('company_id', '=', company_id),
                    ('active', '=', True),
                ])
            pending = stages_by_company[company_id] - invoice.sent_reminder_stage_ids
            elapsed = (today - invoice.invoice_date_due).days
            for stage in pending:
                due = (elapsed == stage.days_offset if stage.days_offset <= 0
                       else elapsed >= stage.days_offset)
                if due:
                    stage.mail_template_id.send_mail(invoice.id, force_send=False)
                    invoice.write({
                        'sent_reminder_stage_ids': [(4, stage.id)],
                        'last_reminder_date': fields.Datetime.now(),
                    })
