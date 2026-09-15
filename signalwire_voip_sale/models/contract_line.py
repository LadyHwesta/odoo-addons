# -*- coding: utf-8 -*-
from odoo import fields, models


class ContractLine(models.Model):
    """Extends the vendored OCA contract module's own contract.line -
    the actual metered-billing mechanism. No new cron needed: this
    hooks into contract's own existing recurring-invoice cron by
    overriding _prepare_invoice_line, which that cron already calls
    for every due line regardless of what generates its price.
    """
    _inherit = 'contract.line'

    is_signalwire_metered = fields.Boolean(
        help="If set, this line's price_unit is ignored - it gets "
             "computed fresh at invoice time by summing real, priced "
             "signalwire.cdr records for the period being invoiced. "
             "Should always be paired with "
             "recurring_invoicing_type='post-paid' (invoice AFTER the "
             "period, once the real cost is known - a metered line "
             "can't be billed in advance the way a flat fee can).")
    signalwire_subproject_id = fields.Many2one(
        'signalwire.subproject',
        help="Whose usage this line bills - required when "
             "is_signalwire_metered is set.")
    signalwire_period_start = fields.Date(
        readonly=True, copy=False,
        help="The exact period this line's most recent invoice "
             "covered - captured at _prepare_invoice_line time since "
             "contract's own last_date_invoiced/recurring_next_date "
             "get advanced past it before the invoice-linking/CDR-"
             "statement step (in account.move) gets a chance to look "
             "it up otherwise.")
    signalwire_period_end = fields.Date(readonly=True, copy=False)

    def _prepare_invoice_line(self):
        vals = super()._prepare_invoice_line()
        if self.is_signalwire_metered and vals and self.signalwire_subproject_id:
            first_date, last_date, _next_date = self._get_period_to_invoice(
                self.last_date_invoiced, self.recurring_next_date)
            if first_date and last_date:
                self.write({
                    'signalwire_period_start': first_date,
                    'signalwire_period_end': last_date,
                })
                cdrs = self.signalwire_subproject_id._sync_cdrs(
                    self, first_date, last_date)
                vals['price_unit'] = sum(cdrs.mapped('billed_amount'))
        return vals
