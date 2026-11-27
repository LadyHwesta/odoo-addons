# -*- coding: utf-8 -*-
{
    'name': 'Support Requests',
    'version': '19.0.1.0.0',
    'category': 'Productivity',
    'summary': "Report a problem from anywhere in Odoo; your team triages it and escalates to your provider",
    'description': """
Support Requests and Escalation
===============================

Anyone can report a problem from the user menu (Report a problem): what's
wrong, what they were trying to do, how urgent it is, with the page they were
on captured for them. The company's support coordinators get it, solve it
in-house or escalate it to their Odoo provider's support by email. The
provider's replies come back into the request, which everyone involved
follows. See ``README.md``.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'images': ['static/description/banner.png'],
    'support': 'sales@meskis.net',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['mail', 'base_setup'],
    'data': [
        'security/support_request_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'wizard/support_request_escalate_views.xml',
        'views/support_request_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'support_request_escalation/static/src/js/*',
        ],
    },
    'application': True,
    'installable': True,
}
