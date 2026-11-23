# -*- coding: utf-8 -*-
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Form 1099-NEC threshold: $600 through payments made in 2025; the One Big
# Beautiful Bill Act raised it to $2,000 for payments made from 1 January
# 2026, indexed for inflation from 2027. Set later years' figures in
# Settings > Technical > System Parameters as l10n_us_1099_nec.threshold.<year>.
THRESHOLDS = {2025: 600.0, 2026: 2000.0}


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    reported_on_1099k = fields.Boolean(
        string='Payments Reported on 1099-K',
        help="Payments made through this journal go through a card network or a "
             "payment app, which reports them on Form 1099-K. They are left out of 1099-NEC.")


class Form1099NecSummary(models.TransientModel):
    _name = 'form.1099.nec.summary'
    _description = 'Form 1099-NEC Summary'

    year = fields.Integer(required=True, default=lambda self: fields.Date.today().year - 1)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    threshold = fields.Float(compute='_compute_threshold')
    line_ids = fields.One2many('form.1099.nec.summary.line', 'summary_id', readonly=True)

    @api.depends('year')
    def _compute_threshold(self):
        params = self.env['ir.config_parameter'].sudo()
        for summary in self:
            override = params.get_param(f'l10n_us_1099_nec.threshold.{summary.year}')
            if override:
                summary.threshold = float(override)
            elif summary.year in THRESHOLDS:
                summary.threshold = THRESHOLDS[summary.year]
            else:
                summary.threshold = THRESHOLDS[2025] if summary.year < 2025 else THRESHOLDS[2026]

    def _nec_vendors(self):
        nec = self.env.ref('l10n_us_form_1099.1099_type_nec', raise_if_not_found=False)
        domain = [('is_1099', '=', True)]
        if nec:
            domain.append(('type_1099_id', '=', nec.id))
        return self.env['res.partner'].search(domain)

    def _payments(self, vendor):
        return self.env['account.payment'].search([
            ('partner_id', 'child_of', vendor.commercial_partner_id.id),
            ('payment_type', '=', 'outbound'),
            ('state', 'in', ('paid', 'in_process')),
            ('date', '>=', date(self.year, 1, 1)),
            ('date', '<=', date(self.year, 12, 31)),
            ('company_id', '=', self.company_id.id),
            ('journal_id.reported_on_1099k', '=', False),
        ])

    @api.model
    def _issues(self, vendor):
        issues = []
        if not vendor.vat:
            issues.append(_("no taxpayer ID (collect a Form W-9)"))
        if not (vendor.street and vendor.city and vendor.state_id and vendor.zip):
            issues.append(_("incomplete address"))
        return issues

    def action_compute(self):
        self.ensure_one()
        self.line_ids.unlink()
        lines = []
        for vendor in self._nec_vendors():
            payments = self._payments(vendor)
            if not payments:
                continue
            total = sum(abs(p.amount_company_currency_signed) for p in payments)
            lines.append({
                'summary_id': self.id,
                'vendor_id': vendor.id,
                'amount': total,
                'payment_count': len(payments),
                'issues': '; '.join(self._issues(vendor)),
            })
        self.env['form.1099.nec.summary.line'].create(lines)
        return {
            'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
            'view_mode': 'form', 'target': 'current', 'name': _('1099-NEC Summary %(y)s', y=self.year),
        }

    def action_print_statements(self):
        self.ensure_one()
        due = self.line_ids.filtered('must_file')
        if not due:
            raise UserError(_("No contractor reached the %(t)s threshold for %(y)s.",
                              t=f'${self.threshold:,.0f}', y=self.year))
        return self.env.ref('l10n_us_form_1099_nec_summary.action_report_1099_nec_statement').report_action(due)


class Form1099NecSummaryLine(models.TransientModel):
    _name = 'form.1099.nec.summary.line'
    _description = 'Form 1099-NEC Summary Line'
    _order = 'amount desc'

    summary_id = fields.Many2one('form.1099.nec.summary', required=True, ondelete='cascade')
    vendor_id = fields.Many2one('res.partner', string='Contractor', readonly=True)
    vat = fields.Char(related='vendor_id.vat', string='Taxpayer ID')
    amount = fields.Float(string='Box 1: Nonemployee Compensation', readonly=True)
    payment_count = fields.Integer(string='Payments', readonly=True)
    must_file = fields.Boolean(compute='_compute_must_file', string='1099-NEC Needed')
    issues = fields.Char(readonly=True)
    year = fields.Integer(related='summary_id.year')
    company_id = fields.Many2one(related='summary_id.company_id')

    @api.depends('amount', 'summary_id.threshold')
    def _compute_must_file(self):
        for line in self:
            line.must_file = line.amount >= line.summary_id.threshold

    def _masked_tin(self):
        digits = ''.join(ch for ch in (self.vat or '') if ch.isdigit())
        return f'***-**-{digits[-4:]}' if len(digits) >= 4 else ''
