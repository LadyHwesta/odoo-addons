# -*- coding: utf-8 -*-
from odoo import _, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    """Ties a sale order to deployment.instance - mirrors
    hestiacp_hosting's/namecheap_domains_sale's/signalwire_voip_sale's
    own _action_confirm override exactly, but deliberately stops one
    step earlier than those three: it creates the deployment.instance
    record and schedules an activity for the salesperson, rather than
    calling action_request() itself. Unlike a hosting package or a
    domain name, the customer's actual domain/database name genuinely
    aren't known from the order alone - action_request() (see
    deployment_instance.py's own guard) won't proceed without them,
    so there's a real, unavoidable "confirm details with the
    customer" step here that the other three checkout flows don't
    need. This module has no public storefront for managed instances
    (unlike /domains or /voip) - selling one is a Sales-app quote,
    staff-driven throughout, matching how the deployment checklist
    itself already works.
    """
    _inherit = 'sale.order'

    def _action_confirm(self):
        result = super()._action_confirm()
        for order in self:
            order._managed_odoo_provision_lines()
        return result

    def _managed_odoo_provision_lines(self):
        self.ensure_one()
        hosting_lines = self.order_line.filtered(
            lambda line: line.product_id.product_tmpl_id.is_managed_odoo_hosting)
        if not hosting_lines:
            return

        app_ids = self.env['deployment.app'].search([
            ('product_template_id', 'in', self.order_line.product_id.product_tmpl_id.ids),
        ])

        for line in hosting_lines:
            template = line.product_id.product_tmpl_id
            server = self._managed_odoo_server_for(template)
            instance = self.env['deployment.instance'].create({
                'partner_id': self.partner_id.id,
                'server_id': server.id,
                'app_ids': [(6, 0, app_ids.ids)],
                'admin_email': self.partner_id.email or False,
                'company_name': self.partner_id.name,
            })
            instance.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=(self.user_id or self.env.user).id,
                summary=_(
                    "New Managed Odoo Instance purchased - %(partner)s",
                    partner=self.partner_id.name),
                note=_(
                    "From order %(order)s. Confirm the customer's domain "
                    "and pick a database name, fill them in on this "
                    "instance, then click Request to generate the "
                    "deployment checklist.", order=self.name))

    def _managed_odoo_server_for(self, template):
        self.ensure_one()
        if template.managed_odoo_hosting_kind == 'dedicated':
            return self.env['deployment.server'].create({
                'name': _("%(partner)s VPS", partner=self.partner_id.name),
                'kind': 'dedicated',
                'partner_id': self.partner_id.id,
            })
        server = self.env['deployment.server'].search([('kind', '=', 'shared')], limit=1)
        if not server:
            raise UserError(_(
                "No shared deployment.server exists yet - create the "
                "one shared server record before selling shared "
                "managed-Odoo hosting."))
        return server
