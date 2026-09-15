# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_managed_odoo_hosting = fields.Boolean(
        string="Is Managed Odoo Hosting",
        help="Selling this product creates a deployment.instance (and, "
             "for the dedicated tier, a new deployment.server) on "
             "order confirmation - see managed_odoo_hosting_kind for "
             "which. This is the \"hosting tier\" line, separate from "
             "any deployment.app products bundled onto the same order "
             "(each of those becomes one of the new instance's "
             "app_ids, not an instance of its own).")
    managed_odoo_hosting_kind = fields.Selection(
        [('shared', 'Shared Multi-Tenant'), ('dedicated', 'Dedicated VPS')],
        string="Hosting Kind",
        help="'Shared' reuses the existing kind='shared' "
             "deployment.server (there should only ever be one); "
             "'dedicated' creates a brand new deployment.server for "
             "this customer.")
