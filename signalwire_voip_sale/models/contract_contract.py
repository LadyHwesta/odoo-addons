# -*- coding: utf-8 -*-
from odoo import models


class ContractContract(models.Model):
    _inherit = 'contract.contract'

    def _recurring_create_invoice(self, date_ref=False):
        """After contract's own invoice creation runs (which, for a
        metered line, already priced it via contract.line's own
        _prepare_invoice_line override), link that period's CDR
        records to the resulting invoice line and attach a proper CDR
        statement PDF - has to happen here, after the fact, because
        the account.move/account.move.line don't exist yet at
        _prepare_invoice_line time.
        """
        moves = super()._recurring_create_invoice(date_ref=date_ref)
        moves._attach_signalwire_cdr_statements()
        return moves
