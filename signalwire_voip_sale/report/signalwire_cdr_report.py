# -*- coding: utf-8 -*-
from odoo import api, models


class SignalWireCdrStatementReport(models.AbstractModel):
    _name = 'report.signalwire_voip_sale.cdr_statement_document'
    _description = 'SignalWire CDR Statement Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        return {
            'doc_ids': docids,
            'doc_model': 'account.move',
            'docs': self.env['account.move'].browse(docids),
            'cdrs': self.env['signalwire.cdr'].browse(data.get('cdr_ids', [])),
            'contract_line': self.env['contract.line'].browse(
                data.get('contract_line_id')),
        }
