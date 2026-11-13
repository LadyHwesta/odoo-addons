# -*- coding: utf-8 -*-
{
    'name': 'VoIP',
    'version': '19.0.1.11.0',
    'category': 'Productivity/VOIP',
    'summary': 'Phone service: accounts, sub-accounts and phone numbers',
    'description': """
VoIP
====

The foundation of the phone system: the connection to your phone
provider, sub-accounts, and phone numbers (search, buy, release).
Calling, voicemail and text messages are added by the other VoIP
modules.

- **Phone Accounts**: the connection settings and a connection test.
- **Sub-accounts**: one per customer, keeping their numbers and calls
  separate.
- **Phone Numbers**: search, buy and release numbers.

Provider setup notes are in ``README.md``.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['mail'],
    'data': [
        'security/ir.model.access.csv',
        'security/signalwire_phone_number_security.xml',
        'wizards/signalwire_phone_number_search_views.xml',
        'views/signalwire_server_views.xml',
        'views/signalwire_subproject_views.xml',
        'views/signalwire_phone_number_views.xml',
        'views/signalwire_e911_views.xml',
        'data/ir_cron_e911.xml',
        'views/signalwire_dashboard_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'signalwire_voip/static/src/dashboard/voip_dashboard.esm.js',
            'signalwire_voip/static/src/dashboard/voip_dashboard.xml',
            'signalwire_voip/static/src/dashboard/voip_dashboard.scss',
        ],
    },
    'installable': True,
    'application': False,
}
