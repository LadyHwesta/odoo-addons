# -*- coding: utf-8 -*-
{
    'name': 'Mailing List Welcome Email',
    'version': '19.0.1.0.0',
    'category': 'Marketing/Email Marketing',
    'summary': 'Send a welcome email, with an unsubscribe link, to each new website signup',
    'description': """
Mailing List Welcome Email
==========================

Pick an Email Marketing mailing as a list's Welcome Email. Everyone who
signs up for that list through a website newsletter block then gets it
once, with Odoo's normal per-recipient unsubscribe link and one-click
unsubscribe headers. If someone signs up an address that isn't theirs,
its owner can leave the list with one click.

See ``README.md``.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['website_mass_mailing'],
    'data': [
        'views/mailing_list_views.xml',
    ],
    'installable': True,
    'application': False,
}
