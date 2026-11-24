# -*- coding: utf-8 -*-
{
    'name': 'Managed Odoo Stripe Connect - Client',
    'version': '19.0.1.3.0',
    'category': 'Accounting/Payment',
    'summary': "Charge customers through Meskis' own Stripe Connect bridge",
    'description': """
Managed Odoo Stripe Connect - Client
========================================

Installed on a managed Odoo instance customer's own separate database
(deployed as part of their ``managed_odoo_instances`` app bundle) -
the other half of ``managed_odoo_stripe_connect``, which lives in
Meskis' own Odoo. Has zero standalone value outside that relationship:
every call it makes goes to Meskis' own bridge, using a bearer token
scoped to this instance's own Stripe Connect account, never Meskis'
Stripe Platform secret (which structurally can't live here at all -
see the other module's own docstring for why).

Settings > General Settings gets three fields (Bridge URL, Bridge
Token, Stripe Account ID) - filled in once during setup from
whatever Meskis hands you, plus a **Set up Stripe payments** button that
opens Stripe's own setup form through the bridge (live-tested against
the Stripe sandbox 2026-11-23, with a real bridged charge and fee).

Stripe providers get **Take payments through Meskis**: core
``payment_stripe``'s own checkout then runs through the bridge (every
Stripe call relayed, Stripe.js loaded on the customer's own account,
payment updates forwarded) with no Stripe secret key on this database.
See README.md.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['base_setup', 'payment_stripe'],
    'data': [
        'data/ir_cron.xml',
        'views/res_config_settings_views.xml',
        'views/payment_provider_views.xml',
        'views/payment_stripe_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'managed_odoo_stripe_connect_client/static/src/interactions/stripe_options.js',
        ],
    },
    'installable': True,
    'application': False,
}
