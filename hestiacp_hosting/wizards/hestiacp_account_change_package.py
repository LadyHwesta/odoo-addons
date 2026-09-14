# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class HestiaCPAccountChangePackage(models.TransientModel):
    """Upgrade or downgrade an active account's package.

    Deliberately doesn't pass HestiaCP's optional FORCE argument to
    ``v-change-user-package`` - verified against the command's own
    source (2026-09-14) that, without it, HestiaCP itself compares the
    account's current usage (web/DNS/mail domains, databases, cron
    jobs, disk, bandwidth) against the new package's limits and refuses
    the change outright if any of them don't fit, with a specific
    "Package doesn't cover ... usage" error - exactly the downgrade
    safety check a customer needs (remove the excess domains/mailboxes/
    etc. first), already built into HestiaCP and not something this
    module needs to reimplement.
    """
    _name = 'hestiacp.account.change.package'
    _description = "Change a HestiaCP Account's Package"

    account_id = fields.Many2one('hestiacp.account', required=True, readonly=True)
    server_id = fields.Many2one(related='account_id.server_id', readonly=True)
    current_product_id = fields.Many2one(
        related='account_id.product_id', string="Current Package", readonly=True)
    new_product_id = fields.Many2one(
        'product.template', string="New Package", required=True,
        domain="[('is_hosting_package', '=', True), "
               "('hestiacp_server_id', '=', server_id), "
               "('id', '!=', current_product_id)]",
        help="Only packages on the same HestiaCP server as the account "
             "are offered - moving an account to a different server "
             "isn't supported by this wizard.")

    def action_confirm(self):
        self.ensure_one()
        account = self.account_id
        new_product = self.new_product_id

        if account.state != 'active':
            raise UserError(_(
                "%(username)s is not active - only an active account's "
                "package can be changed.", username=account.username))
        if new_product == account.product_id:
            raise UserError(_(
                "%(username)s is already on this package.", username=account.username))
        if new_product.hestiacp_server_id != account.server_id:
            raise UserError(_(
                "The new package must be on the account's own server "
                "(%(server)s).", server=account.server_id.name))
        if not new_product.hestiacp_package_name:
            raise UserError(_(
                "%(product)s has no HestiaCP package name set - configure "
                "it on the product before assigning it.", product=new_product.name))

        old_product = account.product_id
        client = account.server_id._get_client()
        client.call('v-change-user-package', account.username, new_product.hestiacp_package_name)

        account.product_id = new_product
        account._change_billing_line(new_product)
        account.message_post(body=_(
            "Package changed from %(old)s to %(new)s. HestiaCP's resource "
            "limits applied immediately; billing at the new price starts "
            "at the account's next renewal, not prorated for the "
            "remainder of the current period.",
            old=old_product.name, new=new_product.name))
        return {'type': 'ir.actions.act_window_close'}
