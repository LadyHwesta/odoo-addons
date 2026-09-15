# -*- coding: utf-8 -*-
from odoo import _, models

CDR_REPORT_XML_ID = 'signalwire_voip_sale.action_report_cdr_statement'


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _attach_signalwire_cdr_statements(self):
        """For every metered contract line this move actually invoices,
        link that period's already-priced CDR records to the resulting
        move line (so signalwire.cdr.move_id shows exactly which
        invoice a call/message ended up billed on) and attach a proper
        itemized CDR statement PDF - a real phone bill's own call/
        message detail, not folded into the invoice as one line per
        call.
        """
        for move in self:
            metered_lines = move.invoice_line_ids.contract_line_id.filtered(
                'is_signalwire_metered')
            for line in metered_lines:
                move_line = move.invoice_line_ids.filtered(
                    lambda l, line=line: l.contract_line_id == line)[:1]
                if not move_line or not line.signalwire_period_start:
                    continue
                cdrs = self.env['signalwire.cdr'].search([
                    ('contract_line_id', '=', line.id),
                    ('date', '>=', line.signalwire_period_start),
                    ('date', '<=', line.signalwire_period_end),
                ])
                cdrs.write({'move_line_id': move_line.id})
                move._generate_signalwire_cdr_pdf(line, cdrs)

    def _generate_signalwire_cdr_pdf(self, contract_line, cdrs):
        self.ensure_one()
        pdf_content, _report_type = self.env['ir.actions.report']._render_qweb_pdf(
            CDR_REPORT_XML_ID, res_ids=self.ids,
            data={'cdr_ids': cdrs.ids, 'contract_line_id': contract_line.id})
        self.env['ir.attachment'].create({
            'name': _("CDR Statement - %(line)s.pdf", line=contract_line.name),
            'type': 'binary',
            'raw': pdf_content,
            'res_model': 'account.move',
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })
