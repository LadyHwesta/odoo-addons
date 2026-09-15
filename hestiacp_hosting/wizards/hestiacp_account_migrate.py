# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class HestiaCPAccountMigrate(models.TransientModel):
    """Onboard an existing customer who's already paid another host
    (Planet Hoster, etc.) through some future date, without billing
    them again for time they've already paid for elsewhere.

    Provisions the real HestiaCP account right now - the same
    v-add-user call a normal checkout makes - but the recurring
    contract.line's recurring_next_date is set explicitly to the
    customer's real already-paid-through date instead of today, so
    this module's own invoicing cron leaves it alone until then. This
    works because recurring_next_date, despite being a "computed"
    field, is declared readonly=False and only auto-computed as a
    *default* - an explicit value passed at create() sticks, the same
    way a normal renewal's own advance of that field does later.
    """
    _name = 'hestiacp.account.migrate'
    _description = 'Migrate an Existing Customer onto HestiaCP'

    partner_id = fields.Many2one('res.partner', required=True)
    product_id = fields.Many2one(
        'product.template', string="Hosting Package", required=True,
        domain=[('is_hosting_package', '=', True)])
    server_id = fields.Many2one(related='product_id.hestiacp_server_id', readonly=True)
    username = fields.Char(
        help="Leave blank to auto-generate one the same way a normal "
             "checkout does. Set this to preserve the username the "
             "customer's already used to on their old host, if it's "
             "available on this server.")
    next_renewal_date = fields.Date(
        required=True,
        help="When the customer's already-paid-for period with their "
             "old host actually ends. Billing in Odoo starts here, not "
             "today - nothing is invoiced or charged before this date.")

    def action_migrate(self):
        self.ensure_one()
        product = self.product_id
        if not product.hestiacp_package_name:
            raise UserError(_(
                "%(product)s has no HestiaCP package name set - configure "
                "it on the product before migrating a customer onto it.",
                product=product.name))

        contract = self.env['contract.contract'].create({
            'name': f'{product.name} - {self.partner_id.name}',
            'partner_id': self.partner_id.id,
            'pricelist_id': self.partner_id.property_product_pricelist.id,
            'company_id': self.env.company.id,
            'contract_type': 'sale',
            'line_recurrence': True,
            'contract_line_ids': [(0, 0, {
                'product_id': product.product_variant_id.id,
                'name': product.name,
                'quantity': 1,
                'price_unit': product.list_price,
                'date_start': fields.Date.context_today(self),
                'recurring_interval': 1,
                'recurring_rule_type': product.hestiacp_billing_period,
                'recurring_invoicing_type': 'pre-paid',
                'recurring_next_date': self.next_renewal_date,
            })],
        })
        account = self.env['hestiacp.account'].create({
            'partner_id': self.partner_id.id,
            'server_id': self.server_id.id,
            'product_id': product.id,
            'contract_id': contract.id,
            'username': self.username or False,
        })
        account.action_provision()
        account.message_post(body=_(
            "Migrated from an existing host - HestiaCP account "
            "provisioned today; billing deferred to the customer's "
            "already-paid-through date of %(date)s.",
            date=self.next_renewal_date))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hestiacp.account',
            'view_mode': 'form',
            'res_id': account.id,
        }
