# -*- coding: utf-8 -*-
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class AccountAccount(models.Model):
    _inherit = 'account.account'

    @api.model
    def _retype_retained_earnings(self, companies=None):
        """Odoo 19's generic chart (also the US one) ships two accounts of the
        Current Year Earnings type: 999999 Profit or Loss Appropriation and
        999998 Accumulated Retained Earnings. Retained earnings carry over from
        year to year, so they belong in ordinary Equity; and reports that need
        exactly one Current Year Earnings account (such as the Trial Balance and
        General Ledger) refuse to run while there are two. Only the chart's own
        retained earnings account is changed, and only while another Current
        Year Earnings account remains."""
        Data = self.env['ir.model.data'].sudo()
        for company in companies or self.env['res.company'].search([]):
            unaffected = self.with_company(company).search([
                *self._check_company_domain(company), ('account_type', '=', 'equity_unaffected')])
            if len(unaffected) < 2:
                continue
            ids = Data.search([('model', '=', 'account.account'), ('res_id', 'in', unaffected.ids),
                               ('name', '=like', f'{company.id}\\_%retained\\_earnings')]).mapped('res_id')
            retained = unaffected.filtered(lambda a: a.id in ids)
            if retained and retained != unaffected:
                retained.account_type = 'equity'
                _logger.info("%s: %s is now an ordinary equity account", company.name, retained.mapped('code'))


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    def _post_load_data(self, template_code, company, template_data):
        result = super()._post_load_data(template_code, company, template_data)
        self.env['account.account']._retype_retained_earnings(company or self.env.company)
        return result
