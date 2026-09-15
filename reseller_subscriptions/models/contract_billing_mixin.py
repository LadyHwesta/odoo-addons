# -*- coding: utf-8 -*-
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class ContractBillingMixin(models.AbstractModel):
    """Shared "auto-charge this record's saved payment token against
    its own contract's due invoices" behavior - the exact shape
    ``hestiacp.account`` and ``namecheap.domain`` each already
    implement independently (near line-for-line identical in both:
    ``hestiacp_hosting/models/hestiacp_account.py`` and
    ``namecheap_domains_sale/models/namecheap_domain.py``). Introduced
    here so a NEW consumer (``signalwire.phone_number``, see
    ``signalwire_phone_number.py`` in this module) doesn't become a
    third hand-copied version.

    Deliberately NOT retrofitted onto ``hestiacp.account``/
    ``namecheap.domain`` themselves - both are already live in
    production and already working; nothing about them needs to
    change for this mixin to close SignalWire's gap.

    A consuming model needs three fields of these exact names/types
    already defined on it before adding this mixin: ``contract_id``
    (Many2one ``contract.contract``), ``payment_token_id`` (Many2one
    ``payment.token``), ``partner_id`` (Many2one ``res.partner``) -
    none are declared here, to avoid any risk of redefining a field an
    inheriting model already has.
    """
    _name = 'contract.billing.mixin'
    _description = "Auto-charge a saved payment token for a contract's due invoices"

    def _charge_invoice(self, invoice):
        """Attempt to charge this record's saved payment token for one
        invoice - Odoo's own server-initiated token-charge API
        (``payment.transaction._charge_with_token``), the same
        mechanism ``hestiacp.account``/``namecheap.domain``'s own
        method of this name already uses.
        """
        self.ensure_one()
        token = self.payment_token_id
        tx = self.env['payment.transaction'].sudo().create({
            'provider_id': token.provider_id.id,
            'payment_method_id': token.payment_method_id.id,
            'token_id': token.id,
            'reference': self.env['payment.transaction']._compute_reference(
                token.provider_id.code, prefix=invoice.name),
            'amount': invoice.amount_residual,
            'currency_id': invoice.currency_id.id,
            'partner_id': self.partner_id.id,
            'operation': 'offline',
            'invoice_ids': [(6, 0, invoice.ids)],
        })
        tx._charge_with_token()
        return tx

    def _cron_auto_charge_due_invoices(self):
        """Call on an already-filtered recordset - e.g. from a model-
        specific ``@api.model`` cron-trigger method that does its own
        ``self.search([...])`` first (each consumer's own "active"/
        "still billable" filter differs - ``hestiacp.account`` and
        ``namecheap.domain`` use a ``state`` field,
        ``signalwire.phone_number`` uses the stock ``active`` boolean
        - so that filtering isn't hardcoded here).
        """
        for record in self:
            if not record.contract_id or not record.payment_token_id:
                continue
            due_invoices = record.contract_id._get_related_invoices().filtered(
                lambda m: m.state == 'posted'
                and m.payment_state in ('not_paid', 'partial')
                and not m.transaction_ids)
            for invoice in due_invoices:
                try:
                    record._charge_invoice(invoice)
                except Exception:
                    _logger.exception(
                        "%s: auto-charge attempt failed for %s, invoice %s",
                        record._name, record.display_name, invoice.name)
