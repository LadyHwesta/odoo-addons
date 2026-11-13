# -*- coding: utf-8 -*-
import logging
from datetime import datetime, time, timezone
from decimal import Decimal

from odoo import Command, _, fields, models
from odoo.exceptions import UserError

from .stripe_tax_client import StripeTaxClient

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    stripe_tax_transaction_id = fields.Char(
        string="Stripe Tax Transaction", readonly=True, copy=False,
        help="This invoice's record in Stripe Tax, used for its reports.")
    stripe_tax_reversal_id = fields.Char(
        string="Stripe Tax Reversal", readonly=True, copy=False)
    stripe_tax_pending = fields.Boolean(
        string="Not Recorded in Stripe Tax", readonly=True, copy=False,
        help="Recording this invoice in Stripe Tax failed; use Record in Stripe Tax to retry.")

    # -- which invoices -------------------------------------------------------

    def _stripe_tax_lines(self):
        """Lines Stripe Tax decides on: products with a Stripe tax code."""
        return self.invoice_line_ids.filtered(
            lambda l: l.display_type == 'product' and l.product_id.stripe_tax_code)

    def _stripe_tax_applies(self):
        self.ensure_one()
        return (self.move_type == 'out_invoice'
                and self.company_id.stripe_tax_provider_id
                and bool(self._stripe_tax_lines()))

    def _stripe_client(self):
        return StripeTaxClient(self.company_id.stripe_tax_provider_id)

    @staticmethod
    def _stripe_amount(amount, currency):
        return int(round(amount * 10 ** currency.decimal_places))

    # -- calculation ----------------------------------------------------------

    def _stripe_tax_address(self):
        partner = self.partner_shipping_id or self.partner_id
        if not partner.country_id:
            raise UserError(_(
                "%(customer)s has no country, so Stripe Tax can't work out "
                "the sales tax for %(invoice)s.",
                customer=partner.display_name, invoice=self.display_name))
        if partner.country_id.code in ('US', 'CA') and not partner.zip:
            raise UserError(_(
                "%(customer)s needs a ZIP/postal code before %(invoice)s can "
                "be confirmed: sales tax depends on it.",
                customer=partner.display_name, invoice=self.display_name))
        address = {
            'line1': partner.street, 'line2': partner.street2, 'city': partner.city,
            'state': partner.state_id.code, 'postal_code': partner.zip,
            'country': partner.country_id.code,
        }
        source = 'shipping' if self.partner_shipping_id and self.partner_shipping_id != self.partner_id else 'billing'
        return {key: value for key, value in address.items() if value}, source

    def _stripe_tax_request(self):
        """The Tax Calculation request for this invoice's taxable lines.
        Lines with a zero or negative amount aren't sent (Stripe needs a
        positive amount), so they get no sales tax."""
        self.ensure_one()
        address, source = self._stripe_tax_address()
        currency = self.currency_id
        lines = self._stripe_tax_lines().filtered(lambda l: l.price_subtotal > 0)
        details = {'address': address, 'address_source': source}
        if self.partner_id.commercial_partner_id.stripe_tax_exempt:
            details['taxability_override'] = 'customer_exempt'
        request = {
            'currency': currency.name.lower(),
            'customer_details': details,
            'line_items': [{
                'amount': self._stripe_amount(line.price_subtotal, currency),
                'reference': str(line.id),
                'tax_code': line.product_id.stripe_tax_code,
                'tax_behavior': 'exclusive',
            } for line in lines],
            'expand': ['line_items.data.tax_breakdown'],
        }
        # Tax follows the invoice date. Stripe accepts dates up to 31 days
        # either side of today; outside that, it uses today's rules.
        if self.invoice_date and abs((self.invoice_date - fields.Date.context_today(self)).days) <= 31:
            moment = datetime.combine(self.invoice_date, time(12), tzinfo=timezone.utc)
            request['tax_date'] = int(moment.timestamp())
        return request

    def _stripe_tax_calculate(self):
        """Ask Stripe Tax for this invoice's sales tax and put the rate it
        returns on each line. Returns the calculation."""
        self.ensure_one()
        calculation = self._stripe_client().post('tax/calculations', self._stripe_tax_request())
        rates = {}
        for item in (calculation.get('line_items') or {}).get('data', []):
            rate = sum(
                (Decimal(str((part.get('tax_rate_details') or {}).get('percentage_decimal') or '0'))
                 for part in (item.get('tax_breakdown') or []) if part.get('amount')),
                Decimal('0'))
            rates[item.get('reference')] = float(rate)
        Tax = self.env['account.tax']
        updates = []
        for line in self._stripe_tax_lines():
            other_taxes = line.tax_ids.filtered(lambda t: not t.is_stripe_tax)
            rate = rates.get(str(line.id), 0.0)
            stripe_tax = Tax._stripe_tax_for_rate(self.company_id, rate) if rate else Tax
            new_taxes = other_taxes | stripe_tax
            if new_taxes != line.tax_ids:
                updates.append(Command.update(line.id, {'tax_ids': [Command.set(new_taxes.ids)]}))
        if updates:
            self.write({'invoice_line_ids': updates})
        return calculation

    # -- recording in Stripe --------------------------------------------------

    def _stripe_tax_reference(self, suffix=''):
        """Unique across Stripe, as it requires: the invoice number plus the
        calculation or transaction it belongs to."""
        return f"{self.name} ({self.env.cr.dbname}:{self.id}{':' + suffix if suffix else ''})"

    def _stripe_tax_record(self, calculation):
        """Record the posted invoice in Stripe Tax. Never blocks posting: a
        failure leaves a note and a to-do with a button to retry."""
        self.ensure_one()
        if not calculation:
            return
        if not calculation.get('tax_amount_exclusive') and not self.company_id.stripe_tax_record_all:
            return
        try:
            transaction = self._stripe_client().post(
                'tax/transactions/create_from_calculation',
                {'calculation': calculation['id'],
                 'reference': self._stripe_tax_reference(calculation['id']),
                 'metadata': {'odoo_invoice': self.name}},
                idempotency_key=f"odoo-stripe-tax-{self.env.cr.dbname}-{self.id}-{calculation['id']}")
        except UserError as exc:
            self._stripe_tax_flag(_("Not recorded in Stripe Tax: %(error)s", error=exc.args[0]))
            return
        self.write({'stripe_tax_transaction_id': transaction.get('id'), 'stripe_tax_pending': False})

    def _stripe_tax_flag(self, message):
        already_flagged = self.stripe_tax_pending
        self.stripe_tax_pending = True
        self.message_post(body=message)
        if already_flagged:
            return
        self.activity_schedule(
            'mail.mail_activity_data_todo', summary=_("Record in Stripe Tax"), note=message,
            user_id=self.invoice_user_id.id or self.env.user.id)

    def action_stripe_tax_record(self):
        """Retry: calculate again and record a posted invoice in Stripe Tax."""
        for move in self.filtered(lambda m: m.state == 'posted' and m.stripe_tax_pending):
            if move.move_type == 'out_refund':
                move._stripe_tax_refund()
            else:
                calculation = move._stripe_client().post('tax/calculations', move._stripe_tax_request())
                move._stripe_tax_record(calculation)
                if not calculation.get('tax_amount_exclusive'):
                    move.stripe_tax_pending = False
            if not move.stripe_tax_pending:
                move.activity_ids.filtered(lambda a: a.summary == _("Record in Stripe Tax")).action_done()

    def _stripe_tax_reverse(self, transaction_id, reference, flat_amount=None):
        data = {'original_transaction': transaction_id, 'reference': reference,
                'mode': 'partial' if flat_amount is not None else 'full'}
        if flat_amount is not None:
            data['flat_amount'] = flat_amount
        return self._stripe_client().post(
            'tax/transactions/create_reversal', data,
            idempotency_key=f"odoo-stripe-tax-rev-{self.env.cr.dbname}-{self.id}-{transaction_id}")

    # -- hooks ----------------------------------------------------------------

    def _post(self, soft=True):
        calculations = {}
        for move in self.filtered(lambda m: m.state == 'draft' and m._stripe_tax_applies()):
            calculations[move.id] = move._stripe_tax_calculate()
        posted = super()._post(soft=soft)
        for move in posted:
            if move.id in calculations:
                move._stripe_tax_record(calculations[move.id])
            elif move.move_type == 'out_refund' and move.reversed_entry_id.stripe_tax_transaction_id:
                move._stripe_tax_refund()
        return posted

    def _stripe_tax_refund(self):
        """A credit note on a recorded invoice reverses it in Stripe Tax:
        fully when it credits the whole invoice, otherwise by its total."""
        self.ensure_one()
        original = self.reversed_entry_id
        full = self.currency_id.is_zero(self.amount_total - original.amount_total)
        try:
            reversal = self._stripe_tax_reverse(
                original.stripe_tax_transaction_id,
                self._stripe_tax_reference(original.stripe_tax_transaction_id),
                None if full else -self._stripe_amount(self.amount_total, self.currency_id))
        except UserError as exc:
            self._stripe_tax_flag(_("Credit not reversed in Stripe Tax: %(error)s", error=exc.args[0]))
            return
        self.write({'stripe_tax_reversal_id': reversal.get('id'), 'stripe_tax_pending': False})

    def button_draft(self):
        """Resetting a recorded invoice to draft reverses it in Stripe Tax,
        so confirming it again records it afresh."""
        for move in self.filtered('stripe_tax_transaction_id'):
            reversal = move._stripe_tax_reverse(
                move.stripe_tax_transaction_id,
                move._stripe_tax_reference(f"reset-{move.stripe_tax_transaction_id}"))
            move.message_post(body=_("Reversed in Stripe Tax (%(id)s) on reset to draft.",
                                     id=reversal.get('id')))
            move.stripe_tax_transaction_id = False
        return super().button_draft()
