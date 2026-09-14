# -*- coding: utf-8 -*-
import logging
import re
import secrets
import string
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

SUSPEND_GRACE_DAYS = 7
TERMINATE_GRACE_DAYS = 30


def _generate_password(length=16):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


class HestiaCPAccount(models.Model):
    """Tracks one customer's HestiaCP hosting account and its lifecycle,
    separately from the sale.order/contract.contract that pay for it -
    the account can outlive any one order (a renewal creates a new
    invoice on the same contract, not a new account).
    """
    _name = 'hestiacp.account'
    _description = 'HestiaCP Hosting Account'
    _inherit = ['mail.thread']
    _rec_name = 'username'

    partner_id = fields.Many2one('res.partner', required=True, index=True)
    server_id = fields.Many2one('hestiacp.server', required=True)
    product_id = fields.Many2one('product.template', required=True, string="Package")
    sale_order_id = fields.Many2one('sale.order', string="Originating Order")
    contract_id = fields.Many2one('contract.contract', string="Billing Contract")
    payment_token_id = fields.Many2one(
        'payment.token', string="Saved Payment Method",
        help="Captured from the checkout order's own transaction, if the "
             "customer tokenized their card there. Renewal invoices get an "
             "automatic charge attempt against this token; with no token "
             "(e.g. they paid by bank transfer, or declined to save a "
             "card), renewals just wait for a manual payment, same as "
             "before this existed.")
    username = fields.Char(help="The account's login name on the HestiaCP server.")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('terminated', 'Terminated'),
    ], default='draft', required=True, tracking=True)
    control_panel_url = fields.Char(compute='_compute_control_panel_url')
    suspended_date = fields.Date(
        help="When this account was last suspended - termination is gated "
             "on time actually spent suspended, not on raw invoice-overdue "
             "days, so an account that's been overdue a very long time before "
             "ever being noticed (e.g. after a cron outage) still gets a "
             "full grace period suspended before deletion, never straight "
             "to termination in one pass.")
    aup_agreement_id = fields.Many2one(
        'hestiacp.agreement', string="Agreement Accepted", readonly=True,
        help="Which version of the Hosting Service Agreement the customer "
             "accepted before this account was billed and provisioned - "
             "copied from the originating order. Empty means no checkout "
             "acceptance page was ever shown (e.g. a backend-confirmed "
             "quote), which action_provision notes on the chatter below.")
    aup_accepted_on = fields.Datetime(readonly=True)
    aup_accepted_ip = fields.Char(readonly=True)

    @api.depends('server_id.hostname')
    def _compute_control_panel_url(self):
        for account in self:
            account.control_panel_url = account.server_id.hostname or False

    def _generate_username(self):
        """A HestiaCP username: lowercase alphanumeric, starting with a
        letter, unique on the target server. Derived from the partner's
        name/email rather than left to chance, so it's recognizable in
        HestiaCP's own admin UI later.
        """
        self.ensure_one()
        base = re.sub(r'[^a-z0-9]', '', (self.partner_id.name or 'user').lower())[:12]
        if not base or not base[0].isalpha():
            base = 'u' + base
        existing = self.env['hestiacp.account'].search([
            ('server_id', '=', self.server_id.id),
            ('username', 'like', f'{base}%'),
        ]).mapped('username')
        if base not in existing:
            return base
        n = 2
        while f'{base}{n}' in existing:
            n += 1
        return f'{base}{n}'

    def action_provision(self):
        """Create the account on HestiaCP: a new user, assigned the
        product's package, with a freshly generated password mailed to
        the customer (never stored in Odoo). Safe to call only from
        'draft' - re-provisioning an active account would just fail
        against HestiaCP with a "user already exists" error, which is
        the right outcome rather than silently no-op'ing.
        """
        for account in self:
            if account.state != 'draft':
                raise UserError(_(
                    "%(username)s is not in Draft - only a new account can be "
                    "provisioned.", username=account.username or account.partner_id.name))
            if not account.product_id.hestiacp_package_name:
                raise UserError(_(
                    "%(product)s has no HestiaCP package name set - configure "
                    "it on the product before selling it.", product=account.product_id.name))

            account.username = account.username or account._generate_username()
            password = _generate_password()
            client = account.server_id._get_client()
            # v-add-user's real signature (verified 2026-09-14 against a
            # live server): USER PASSWORD EMAIL [PACKAGE] [NAME] [LASTNAME]
            # - the package is assigned right here, no separate
            # v-change-user-package call needed on first provisioning.
            client.call('v-add-user', account.username, password,
                        account.partner_id.email or '',
                        account.product_id.hestiacp_package_name,
                        account.partner_id.name or '')
            account.state = 'active'
            if not account.aup_accepted_on:
                account.message_post(body=_(
                    "No Hosting Service Agreement acceptance is on record "
                    "for this account - it wasn't provisioned through the "
                    "website checkout's agreement page. Confirm the "
                    "customer agreed some other way (a signed quote, a "
                    "phone order, etc.) before relying on this account."))
            account._send_credentials_email(password)

    def _send_credentials_email(self, password):
        self.ensure_one()
        template = self.env.ref(
            'hestiacp_hosting.mail_template_account_provisioned', raise_if_not_found=False)
        if not template:
            return
        template.with_context(hestiacp_password=password).send_mail(
            self.id, force_send=True)

    def _change_billing_line(self, new_product):
        """Switch this account's recurring billing over to `new_product`,
        effective at the *next* renewal - not prorated for whatever's
        left of the period already paid for under the old package. The
        HestiaCP-side package change (see
        hestiacp.account.change.package) takes effect immediately
        regardless; only the price charged going forward is deferred,
        which keeps this simple (no partial-period credit/charge math)
        at the cost of a small, deliberate mismatch for the remainder
        of the current period - the account has the new package's
        resources but is still billed at the old price for it, in
        either direction (upgrade or downgrade).

        No-op if the account has no contract (shouldn't happen for an
        active account, but defensive) or no still-open contract line
        to end.
        """
        self.ensure_one()
        if not self.contract_id:
            return
        today = fields.Date.context_today(self)
        old_line = self.contract_id.contract_line_ids.filtered(
            lambda line: not line.date_end or line.date_end >= today)[:1]
        if not old_line:
            return

        if not old_line.last_date_invoiced:
            # Nothing has ever been invoiced on this line yet (e.g. a
            # same-day change right after provisioning) - there's no
            # already-paid period to preserve, so just repoint the
            # existing line at the new product instead of trying to end
            # it before its own date_start (recurring_next_date equals
            # date_start until the first invoice ever goes out, which
            # would otherwise violate contract.line's own start<=end
            # constraint). The very next invoice is already at the new
            # price in this case, not deferred.
            old_line.write({
                'product_id': new_product.product_variant_id.id,
                'name': new_product.name,
                'price_unit': new_product.list_price,
                'recurring_rule_type': new_product.hestiacp_billing_period,
            })
            return

        effective_date = old_line.recurring_next_date or today
        old_line.date_end = effective_date - timedelta(days=1)
        self.env['contract.line'].create({
            'contract_id': self.contract_id.id,
            'product_id': new_product.product_variant_id.id,
            'name': new_product.name,
            'quantity': old_line.quantity,
            'price_unit': new_product.list_price,
            'date_start': effective_date,
            'recurring_interval': 1,
            'recurring_rule_type': new_product.hestiacp_billing_period,
            'recurring_invoicing_type': 'pre-paid',
        })

    def action_suspend(self):
        for account in self.filtered(lambda a: a.state == 'active'):
            account.server_id._get_client().call('v-suspend-user', account.username)
            account.write({
                'state': 'suspended',
                'suspended_date': fields.Date.context_today(account),
            })

    def action_unsuspend(self):
        for account in self.filtered(lambda a: a.state == 'suspended'):
            account.server_id._get_client().call('v-unsuspend-user', account.username)
            account.write({'state': 'active', 'suspended_date': False})

    def action_terminate(self):
        for account in self.filtered(lambda a: a.state in ('active', 'suspended')):
            account.server_id._get_client().call('v-delete-user', account.username)
            account.state = 'terminated'

    def _overdue_days(self):
        """Days since the oldest unpaid/partially-paid invoice on this
        account's contract became due, or False if nothing's overdue.
        """
        self.ensure_one()
        if not self.contract_id:
            return False
        overdue_moves = self.contract_id._get_related_invoices().filtered(
            lambda m: m.payment_state in ('not_paid', 'partial')
            and m.invoice_date_due)
        if not overdue_moves:
            return False
        oldest_due = min(overdue_moves.mapped('invoice_date_due'))
        return (fields.Date.context_today(self) - oldest_due).days

    def _charge_invoice(self, invoice):
        """Attempt to charge this account's saved payment token for one
        invoice, using Odoo's own server-initiated token-charge API
        (the same ``_charge_with_token`` a saved-card "pay now" button
        uses, just invoked here instead of from a customer click).
        Success/failure is whatever the provider reports - a failure
        here isn't raised, just left for the payment-status cron to
        notice as still-unpaid and suspend on schedule same as a
        customer who never gets charged at all.
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
        """For active accounts with a saved payment token, attempt to
        charge any posted invoice on their contract that hasn't already
        had a charge attempt (successful or not - this makes one attempt
        per invoice, not a retry loop). Called from
        ``_cron_check_payment_status`` before it evaluates suspend/
        unsuspend, so a charge made just now is already reflected in
        that same run - not scheduled as a separate ir.cron, to avoid
        depending on two crons happening to run in the right order.
        """
        for account in self.search([('state', '=', 'active'), ('payment_token_id', '!=', False)]):
            if not account.contract_id:
                continue
            due_invoices = account.contract_id._get_related_invoices().filtered(
                lambda m: m.state == 'posted'
                and m.payment_state in ('not_paid', 'partial')
                and not m.transaction_ids)
            for invoice in due_invoices:
                try:
                    account._charge_invoice(invoice)
                except Exception:
                    _logger.exception(
                        "HestiaCP: auto-charge attempt failed for account %s, invoice %s",
                        account.username, invoice.name)

    @api.model
    def _cron_check_payment_status(self):
        """Attempt to auto-charge any due invoices, then suspend accounts
        whose payment has lapsed past the grace period, unsuspend ones
        that have caught up, and terminate accounts that have been
        suspended too long. Runs daily - see data/ir_cron.xml.
        """
        self._cron_auto_charge_due_invoices()

        for account in self.search([('state', '=', 'active')]):
            overdue = account._overdue_days()
            if overdue and overdue >= SUSPEND_GRACE_DAYS:
                account.action_suspend()

        for account in self.search([('state', '=', 'suspended')]):
            if not account._overdue_days():
                account.action_unsuspend()
            elif account.suspended_date and (
                    fields.Date.context_today(account) - account.suspended_date
            ).days >= TERMINATE_GRACE_DAYS:
                account.action_terminate()
