# -*- coding: utf-8 -*-
{
    'name': 'HestiaCP Hosting Billing',
    'version': '19.0.1.0.0',
    'category': 'Sales',
    'summary': 'Sell hosting packages and auto-provision HestiaCP accounts on payment',
    'description': """
HestiaCP Hosting Billing
==========================

Sells hosting packages through the normal ``website_sale`` storefront,
bills them on a recurring basis via OCA's ``contract`` module (Odoo CE
has no built-in recurring billing - ``sale_subscription`` is
Enterprise-only), and automatically provisions/suspends/terminates the
customer's account on a HestiaCP server via its HTTP API as payment
comes in, lapses, or the plan is cancelled.

**What this module does NOT do**: give customers a single-sign-on link
into HestiaCP - HestiaCP's API has no such facility outside of
phpMyAdmin, so the portal only ever links to HestiaCP's own login
page. Customers authenticate with whatever password they set at
checkout (pushed to HestiaCP via ``v-change-user-password``, never
emailed in plaintext).

See ``README.md`` for the full architecture and setup steps.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['contract', 'contract_sale', 'sale_management', 'website_sale', 'payment'],
    'data': [
        'security/ir.model.access.csv',
        'security/hestiacp_security.xml',
        'data/ir_cron.xml',
        'views/hestiacp_server_views.xml',
        'views/hestiacp_account_views.xml',
        'views/product_template_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
}
