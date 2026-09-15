# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class SignalWirePhoneNumber(models.Model):
    """Closes a real gap: signalwire_voip_sale creates a real
    contract.contract per purchased number at checkout, but (before
    this module) never stored a back-reference to it anywhere, and
    nothing ever captured the checkout's payment token either - so a
    SignalWire customer's invoices were never auto-charged, unlike
    hosting or domains. See signalwire_sale_order.py for the checkout-
    side half of this fix.
    """
    _name = 'signalwire.phone_number'
    _inherit = ['signalwire.phone_number', 'contract.billing.mixin']

    contract_id = fields.Many2one(
        'contract.contract', string="Billing Contract", copy=False,
        help="The recurring rental + metered-usage contract billing "
             "this number - set at checkout, not editable by hand.")
    payment_token_id = fields.Many2one(
        'payment.token', string="Saved Payment Method", copy=False,
        help="Captured from the checkout order's own transaction, if "
             "the customer tokenized their card there - same "
             "mechanism hestiacp.account/namecheap.domain already "
             "use for their own renewals. With no token, this "
             "number's invoices wait for manual payment.")

    def _signalwire_after_provisioned(self, contract, checkout_transaction):
        """Overrides signalwire_voip_sale's own no-op hook (see that
        module's models/signalwire_phone_number.py) - this is the
        actual fix for the gap: stores the contract this checkout just
        created, plus the payment token if the customer tokenized
        their card there, mirroring hestiacp.account/namecheap.domain's
        own checkout-time capture exactly.
        """
        self.ensure_one()
        self.write({
            'contract_id': contract.id,
            'payment_token_id': (
                checkout_transaction.token_id.id if checkout_transaction else False),
        })

    def action_release(self):
        """Extends the base release (still releases the number at
        SignalWire itself, unchanged - see signalwire_voip's own
        action_release) to also stop billing for it: previously the
        contract line kept running after release, so a customer who
        cancelled a number kept being charged for it.
        """
        today = fields.Date.context_today(self)
        open_lines = self.env['contract.line']
        for number in self.filtered('contract_id'):
            open_lines |= number.contract_id.contract_line_ids.filtered(
                lambda line: not line.date_end or line.date_end >= today)
        result = super().action_release()
        if open_lines:
            open_lines.write({'date_end': today})
        return result

    def _subscription_summary(self):
        self.ensure_one()
        line = self.env['contract.line']
        if self.contract_id:
            today = fields.Date.context_today(self)
            line = self.contract_id.contract_line_ids.filtered(
                lambda l: not l.date_end or l.date_end >= today)[:1]
        return {
            'name': _("Phone Number: %(number)s", number=self.name),
            'state': 'active' if self.active else 'released',
            'next_invoice_date': line.recurring_next_date if line else False,
            'monthly_amount': line.price_unit if line else 0.0,
            'can_upgrade': False,
            'can_cancel': self.active,
            'has_payment_method': bool(self.payment_token_id),
            'portal_view_url': f'/my/contracts/{self.contract_id.id}' if self.contract_id else False,
        }

    @api.model
    def _cron_signalwire_auto_charge(self):
        self.search([('active', '=', True), ('payment_token_id', '!=', False)]
                    )._cron_auto_charge_due_invoices()
