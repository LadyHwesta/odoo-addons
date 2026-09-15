# -*- coding: utf-8 -*-
import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

# How many days before expiry the renewal cron starts trying to renew -
# gives a real cushion before the domain actually lapses, and lines up
# with roughly when the contract's own pre-paid renewal invoice becomes
# due (see the cron's own docstring).
RENEW_LEAD_DAYS = 15


class NamecheapDomain(models.Model):
    _inherit = 'namecheap.domain'

    sale_order_id = fields.Many2one('sale.order', string="Originating Order")
    contract_id = fields.Many2one('contract.contract', string="Renewal Billing Contract")
    payment_token_id = fields.Many2one(
        'payment.token', string="Saved Payment Method",
        help="Captured from the checkout order's own transaction, if the "
             "customer tokenized their card there - the same mechanism "
             "hestiacp.account uses for hosting renewals. With no token, "
             "renewal invoices wait for manual payment, and the domain "
             "simply doesn't auto-renew at Namecheap (see the renewal "
             "cron's own docstring for why that's the safe default).")

    def _charge_invoice(self, invoice):
        """Attempt to charge this domain's saved payment token for one
        invoice - identical mechanism to hestiacp.account's own method
        of the same name (Odoo's own server-initiated token-charge API).
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

    @api.model
    def _cron_auto_charge_due_invoices(self):
        for domain in self.search([('state', '=', 'active'), ('payment_token_id', '!=', False)]):
            if not domain.contract_id:
                continue
            due_invoices = domain.contract_id._get_related_invoices().filtered(
                lambda m: m.state == 'posted'
                and m.payment_state in ('not_paid', 'partial')
                and not m.transaction_ids)
            for invoice in due_invoices:
                try:
                    domain._charge_invoice(invoice)
                except Exception:
                    _logger.exception(
                        "Namecheap: auto-charge attempt failed for domain %s, invoice %s",
                        domain.name, invoice.name)

    @api.model
    def _cron_renew_domains(self):
        """Attempt to auto-charge any due renewal invoice, then actually
        renew at Namecheap (domains.renew) any domain that's both fully
        paid through its current period and within RENEW_LEAD_DAYS of
        expiring.

        Deliberately does NOT renew a domain with an unpaid invoice - no
        charge just means no renewal, full stop. Unlike hosting, there's
        no suspend-then-terminate grace period to sit in first: a domain
        has no "still running but degraded" state, it either gets
        renewed at the registrar before it expires or it lapses (subject
        to Namecheap's own post-expiration redemption grace period,
        outside this module's control either way).
        """
        self._cron_auto_charge_due_invoices()
        deadline = fields.Date.context_today(self) + relativedelta(days=RENEW_LEAD_DAYS)
        for domain in self.search([('state', '=', 'active'), ('expires_on', '<=', deadline)]):
            if not domain.contract_id:
                continue
            unpaid = domain.contract_id._get_related_invoices().filtered(
                lambda m: m.payment_state in ('not_paid', 'partial'))
            if unpaid:
                _logger.warning(
                    "Namecheap: %s not renewed - unpaid invoice(s) on its contract",
                    domain.name)
                continue
            sld, tld = domain.name.split('.', 1)
            try:
                domain.server_id.renew_domain(sld, tld, 1)
            except Exception:
                _logger.exception("Namecheap: renewal failed for %s", domain.name)
                continue
            domain.expires_on = domain.expires_on + relativedelta(years=1)
            domain.message_post(body=_(
                "Renewed at Namecheap - now expires %(date)s.", date=domain.expires_on))
