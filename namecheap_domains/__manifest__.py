# -*- coding: utf-8 -*-
{
    'name': 'Namecheap Domain Reselling',
    'version': '19.0.1.0.0',
    'category': 'Sales',
    'summary': 'Sell domains through Namecheap\'s reseller API with a percentage markup',
    'description': """
Namecheap Domain Reselling
============================

**Phase 1 of a multi-phase build** (backend core only - see README for
what's not built yet). Connects to Namecheap's reseller API
(https://www.namecheap.com/support/api/intro/) to check domain
availability and cache Namecheap's own per-TLD pricing, marked up by a
single global percentage. Domain search on the website, checkout, and
actual registration/renewal are not in this phase.

See ``README.md`` for the full architecture, what's verified vs. not,
and what's planned next.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/namecheap_server_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
}
