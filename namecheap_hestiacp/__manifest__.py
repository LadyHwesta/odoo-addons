# -*- coding: utf-8 -*-
{
    'name': 'Namecheap - HestiaCP Bridge',
    'version': '19.0.1.0.0',
    'category': 'Sales',
    'summary': 'Deploy a Namecheap-owned domain onto a HestiaCP hosting account',
    'description': """
Namecheap - HestiaCP Bridge
=============================

A small connecting module - deliberately not merged into either
``namecheap_domains`` or ``hestiacp_hosting`` - since not every
purchased domain will be deployed to HestiaCP, and either module
should stay installable on its own. Adds a "Deploy to HestiaCP" action
on ``namecheap.domain`` that adds it as a web/DNS/mail domain on a
chosen ``hestiacp.account`` via HestiaCP's own ``v-add-domain``.

See ``README.md`` for exactly what this does and doesn't handle (in
particular: this does NOT touch the domain's nameservers at Namecheap -
see the README for why and what's needed for a site to actually go
live).
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['namecheap_domains', 'hestiacp_hosting'],
    'data': [
        'views/namecheap_domain_views.xml',
    ],
    'installable': True,
    'application': False,
}
