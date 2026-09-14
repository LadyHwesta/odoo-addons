# -*- coding: utf-8 -*-
{
    'name': 'HestiaCP Hosting Billing',
    'version': '19.0.1.5.0',
    'category': 'Sales',
    'summary': 'Sell hosting packages and auto-provision HestiaCP accounts on payment',
    'description': """
HestiaCP Hosting Billing
==========================

Sells hosting packages through the normal ``website_sale`` storefront,
bills them on a recurring basis via OCA's ``contract`` module (Odoo CE
has no built-in recurring billing - ``sale_subscription`` is
Enterprise-only), attempts to auto-charge the customer's saved Stripe
card on each renewal, and automatically provisions/suspends/terminates
the customer's account on a HestiaCP server via its HTTP API as
payment comes in, lapses, or the plan is cancelled. A hosting order
can't reach checkout payment until the customer accepts a Hosting
Service Agreement (acceptable use, anti-spam, mandatory unsubscribe),
enforced server-side and recorded with a timestamp/IP/version on the
order and the resulting account.

**What this module does NOT do**: give customers a single-sign-on link
into HestiaCP - HestiaCP's API has no such facility outside of
phpMyAdmin, so the portal only ever links to HestiaCP's own login
page. A random password is generated and emailed once on provisioning
(never stored in Odoo past that message) rather than letting the
customer choose one at checkout.

See ``README.md`` for the full architecture and setup steps.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': [
        'contract', 'contract_sale', 'sale_management', 'website_sale',
        'payment', 'account_payment', 'payment_stripe', 'portal',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/hestiacp_security.xml',
        'data/ir_cron.xml',
        'data/hestiacp_agreement_data.xml',
        'views/hestiacp_server_views.xml',
        'views/hestiacp_account_views.xml',
        'views/hestiacp_account_portal_templates.xml',
        'views/hestiacp_agreement_views.xml',
        'views/hestiacp_agreement_templates.xml',
        'views/product_template_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
}
