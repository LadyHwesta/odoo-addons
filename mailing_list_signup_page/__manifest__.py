# -*- coding: utf-8 -*-
{
    'name': 'Mailing List Signup Page',
    'version': '19.0.1.0.0',
    'category': 'Marketing/Email Marketing',
    'summary': 'A phone-friendly signup page and QR code sign for a mailing list, with a kiosk mode for events',
    'description': """
Mailing List Signup Page
========================

Give a public mailing list its own simple signup page (for example
``/join/news``): a title, a short introduction, a name and an email field.
Print a sign with its QR code for a table at an event, or put the QR code
on your business cards. Kiosk mode lets people sign up one after another
on your own phone or tablet: each signup is forgotten as soon as it's done.

New signups get the list's welcome email (Mailing List Welcome), once per
address. See ``README.md``.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'images': ['static/description/banner.png'],
    'support': 'sales@meskis.net',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['website_mass_mailing', 'mailing_list_welcome'],
    'data': [
        'views/mailing_list_views.xml',
        'views/signup_templates.xml',
        'report/signup_sign_report.xml',
    ],
    'installable': True,
    'application': False,
}
