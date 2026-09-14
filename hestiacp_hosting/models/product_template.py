# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_hosting_package = fields.Boolean(
        help="Selling this creates/renews a HestiaCP account rather than "
             "just an invoice line.")
    hestiacp_server_id = fields.Many2one(
        'hestiacp.server', string="Provisioning Server",
        help="New accounts sold on this package are created on this server.")
    hestiacp_package_name = fields.Char(
        string="HestiaCP Package Name",
        help="The exact name of an existing package on the HestiaCP server "
             "(Server > Packages) - e.g. \"basic\", \"pro\". Must be created "
             "there by hand first: HestiaCP's Access Key permission system "
             "has no category covering v-add-user-package / "
             "v-change-user-package-value / v-list-user-packages (verified "
             "2026-09-14 - none of its 6 built-in categories include them), "
             "so this module can assign an existing package to an account "
             "but can't define or edit the package itself via the API.")
    hestiacp_billing_period = fields.Selection([
        ('monthly', "Monthly"),
        ('quarterly', "Quarterly"),
        ('yearly', "Yearly"),
    ], string="Billing Period", default='monthly',
        help="How often the recurring contract created from this product "
             "invoices - contract's own recurring_rule_type, which already "
             "supports this natively. To offer more than one cadence for "
             "the same plan (e.g. a cheaper annual option), create a "
             "separate product per period, same package/server on each - "
             "there's no single-product cadence picker.")

    # Resource limits, named after HestiaCP's own package fields.
    # Informational only - see hestiacp_package_name's help text above for
    # why these can't be pushed to HestiaCP automatically. Keep this
    # template's values matching whatever's actually configured on the
    # HestiaCP package by hand.
    hestiacp_disk_quota = fields.Integer(string="Disk Quota (MB)", default=1000)
    hestiacp_bandwidth = fields.Integer(string="Bandwidth (MB/month)", default=10000)
    hestiacp_web_domains = fields.Integer(string="Web Domains", default=1)
    hestiacp_dns_domains = fields.Integer(string="DNS Domains", default=1)
    hestiacp_mail_accounts = fields.Integer(string="Mail Accounts", default=5)
    hestiacp_databases = fields.Integer(string="Databases", default=1)
    hestiacp_backups = fields.Integer(string="Backups", default=3)
