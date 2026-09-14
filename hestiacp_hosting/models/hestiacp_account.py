# -*- coding: utf-8 -*-
import re
import secrets
import string

from odoo import _, api, fields, models
from odoo.exceptions import UserError

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
            account._send_credentials_email(password)

    def _send_credentials_email(self, password):
        self.ensure_one()
        template = self.env.ref(
            'hestiacp_hosting.mail_template_account_provisioned', raise_if_not_found=False)
        if not template:
            return
        template.with_context(hestiacp_password=password).send_mail(
            self.id, force_send=True)

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

    @api.model
    def _cron_check_payment_status(self):
        """Suspend accounts whose payment has lapsed past the grace
        period, unsuspend ones that have caught up, and terminate
        accounts that have been suspended too long. Runs daily - see
        data/ir_cron.xml.
        """
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
