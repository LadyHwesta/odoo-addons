# -*- coding: utf-8 -*-
{
    'name': 'DMARC Reports',
    'version': '19.0.1.0.0',
    'category': 'Productivity',
    'summary': 'Read DMARC aggregate reports and explain them in plain language',
    'description': """
Mail providers send daily DMARC aggregate reports to the address in a domain's
DMARC record. Point an Incoming Mail Server at that mailbox, set it to create
DMARC Reports, and this module reads each report, works out who sent mail as
your domain, and tells you in plain language what passes, what fails and what
to fix.
""",
    'author': 'Tiesa',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'license': 'LGPL-3',
    'depends': ['mail', 'base_setup'],
    'data': [
        'security/dmarc_security.xml',
        'security/ir.model.access.csv',
        'data/ir_config_parameter.xml',
        'views/dmarc_record_views.xml',
        'views/dmarc_report_views.xml',
        'views/dmarc_domain_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': True,
}
