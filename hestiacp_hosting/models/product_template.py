# -*- coding: utf-8 -*-
from odoo import api, fields, models


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
        help="The package name as it exists (or will be created) on the "
             "HestiaCP server - e.g. \"basic\", \"pro\". Kept in sync with "
             "the resource limits below via the Sync button.")

    # Resource limits, named after HestiaCP's own package fields so the
    # mapping in _hestiacp_package_values() below is obvious. Not every
    # HestiaCP package field is exposed here - just the ones that make
    # sense to vary per plan; anything else uses HestiaCP's own default
    # template values for a new package.
    hestiacp_disk_quota = fields.Integer(string="Disk Quota (MB)", default=1000)
    hestiacp_bandwidth = fields.Integer(string="Bandwidth (MB/month)", default=10000)
    hestiacp_web_domains = fields.Integer(string="Web Domains", default=1)
    hestiacp_dns_domains = fields.Integer(string="DNS Domains", default=1)
    hestiacp_mail_accounts = fields.Integer(string="Mail Accounts", default=5)
    hestiacp_databases = fields.Integer(string="Databases", default=1)
    hestiacp_backups = fields.Integer(string="Backups", default=3)

    def _hestiacp_package_values(self):
        """Map this template's resource-limit fields to HestiaCP's own
        package field names, for use with v-change-user-package-value.
        """
        self.ensure_one()
        return {
            'DISK_QUOTA': self.hestiacp_disk_quota,
            'BANDWIDTH': self.hestiacp_bandwidth,
            'WEB_DOMAINS': self.hestiacp_web_domains,
            'DNS_DOMAINS': self.hestiacp_dns_domains,
            'MAIL_ACCOUNTS': self.hestiacp_mail_accounts,
            'DATABASES': self.hestiacp_databases,
            'BACKUPS': self.hestiacp_backups,
        }

    def action_hestiacp_sync_package(self):
        """Push this template's resource limits to its HestiaCP server as
        a package definition, creating the package first if needed.

        NOTE: the exact v-add-user-package / v-change-user-package-value
        argument shapes here are based on HestiaCP's documented CLI, not
        yet confirmed against a live server - this is the method to
        re-check first if a real call fails once a server is available
        to test against.
        """
        for template in self:
            if not (template.hestiacp_server_id and template.hestiacp_package_name):
                continue
            client = template.hestiacp_server_id._get_client()
            existing = client.call('v-list-user-packages', 'json')
            if template.hestiacp_package_name not in existing:
                client.call('v-add-user-package', template.hestiacp_package_name)
            for key, value in template._hestiacp_package_values().items():
                client.call('v-change-user-package-value',
                             template.hestiacp_package_name, key, value)
