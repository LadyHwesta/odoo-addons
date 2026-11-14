# -*- coding: utf-8 -*-
{
    'name': 'Managed Odoo Stripe Connect - Client',
    'version': '19.0.1.0.1',
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
whatever Meskis hands you.

**Deliberately scoped as a foundation, not a drop-in replacement for
core Odoo's own payment_stripe checkout flow.** ``StripeConnectBridge
Client.create_payment_intent()`` charges a customer through the
bridge correctly (with Meskis' own fee applied automatically), but
core ``payment_stripe``'s own multi-step flow (customer creation,
setup intents, inline card-entry UI) isn't transparently proxied
through it - only the actual charge is covered here. Wiring this into
a real self-service checkout page (collecting a card via Stripe.js/
Elements, then calling this client) is real follow-on work, not done
yet - see README.md.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['base_setup'],
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
}
