# -*- coding: utf-8 -*-
{
    'name': 'Managed Odoo Instances',
    'version': '19.0.3.0.0',
    'category': 'Sales/Subscriptions',
    'summary': 'Deploy and bill customer Odoo instances - shared multi-tenant or dedicated VPS',
    'description': """
Managed Odoo Instances
========================

Phase 2 of the reseller-subscriptions project (see
``reseller_subscriptions``'s own README for Phase 1). Treats "we run a
dedicated Odoo instance for you" as a billable, trackable product -
shared multi-tenant server for smaller customers, or a dedicated VPS
for anyone who needs their own.

The actual system-level work (nginx vhost, SSL via certbot, database
creation + app install) is done by a small standalone companion agent
- see the separate `meskis-deploy-agent
<https://github.com/LadyHwesta/meskis-deploy-agent>`_ repo - called
from here over HTTPS with a bearer token, the same
``SignalWireClient``/``HestiaCPClient`` pattern already used
throughout this repo. This module never holds SSH credentials or runs
shell commands itself.

- ``deployment.server`` - one record per Odoo-hosting server (the
  single shared multi-tenant box, or one per dedicated customer VPS).
- ``deployment.instance`` - one record per customer database deployed,
  billed through ``reseller_subscriptions``'s own
  ``contract.billing.mixin``. Requesting one generates a real
  ``project.project`` deployment checklist - for a brand-new dedicated
  server, including the one-time bootstrap script as a task attachment
  (sent to Tiesa to run by hand, never to the customer - most aren't
  technical enough for that to make sense). Billing only starts once
  an instance is actually marked live.
- ``deployment.app`` - a small curated catalog (the existing
  nonprofit/club/paramedic suites as presets) mapping to real
  technical module names, each linked to a sellable ``product.template``.

``upcloud.account``/``upcloud_client.py`` optionally automate the one
prerequisite step the bootstrap script itself can't: creating the VPS
in the first place, via UpCloud's real API (live-verified 2026-09-15 -
a real server was created, confirmed reachable over SSH with an
injected key, then destroyed). The bootstrap script - still run by
hand, by Tiesa, never the customer - picks up from there exactly as
before.

Sellable through a normal Sales-app quote: a "hosting tier" product
(``is_managed_odoo_hosting`` on ``product.template`` - shared or
dedicated) creates the ``deployment.instance`` on order confirmation,
picking up any ``deployment.app`` products on the same order as the
apps to install. No public storefront - the customer's actual domain/
database name genuinely aren't known from an order alone, so this
schedules an activity for the salesperson to confirm those and click
Request themselves, rather than pretending to fully automate a step
that needs a real conversation with the customer first.

See README.md for what's still a manual step by design (deeper
per-instance configuration, the X-Odoo-Dbfilter routing middleware
itself) and what's not yet live-verified.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': [
        'reseller_subscriptions', 'project', 'contract', 'contract_sale',
        'sale_management',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/product_template_data.xml',
        'data/deployment_app_data.xml',
        'views/upcloud_account_views.xml',
        'views/deployment_server_views.xml',
        'views/deployment_instance_views.xml',
        'views/deployment_app_views.xml',
        'views/product_template_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
}
