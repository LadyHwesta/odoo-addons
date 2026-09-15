# -*- coding: utf-8 -*-
{
    'name': 'Namecheap Domain Storefront',
    'version': '19.0.1.0.0',
    'category': 'Sales',
    'summary': 'Sell domains through Namecheap on the website, with recurring renewal billing',
    'description': """
Namecheap Domain Storefront
==============================

Phase 2+3 of the domain-reselling build (see ``namecheap_domains``'s
own README for Phase 1): a website search box where a customer finds
and buys a domain, real registration via Namecheap's
``domains.create`` on order confirmation, and yearly recurring renewal
billing (via vendored OCA ``contract``) that actually calls
``domains.renew`` at renewal time rather than just invoicing.

See ``README.md`` for the full flow, known simplifications, and the
live-money risks flagged before turning this on with a production
Namecheap account.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': [
        'namecheap_domains', 'sale_management', 'website_sale',
        'payment', 'account_payment', 'contract', 'contract_sale',
    ],
    'data': [
        'data/ir_cron.xml',
        'views/product_template_views.xml',
        'views/namecheap_domain_views.xml',
        'views/namecheap_server_views.xml',
        'views/domain_search_templates.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'namecheap_domains_sale/static/src/js/domain_search.js',
        ],
    },
    'installable': True,
    'application': False,
}
