# -*- coding: utf-8 -*-
{
    'name': 'Email Templates Menu',
    'version': '19.0.1.0.0',
    'category': 'Discuss',
    'summary': 'A plain Settings menu for editing email templates, no developer mode required',
    'description': """
Email Templates Menu
=====================

Odoo's own Email Templates screen is already simple once you're on
it - the routing/context-action fields are already hidden unless
developer mode is on. The only real obstacle is that the menu to
reach it lives under Settings > Technical, which requires developer
mode (or a permanent "Technical feature" grant) to even see.

This module adds a second, plain menu entry - "Email Templates",
sitting directly under Settings next to General Settings, not nested
under Technical - visible to anyone granted Odoo's own existing "Mail
Template Editor" permission. No new models, no new permissions to
maintain: it just gives that one built-in permission a normal front
door.

See ``README.md`` for how to grant it to a customer.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['mail'],
    'data': [
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
}
