# -*- coding: utf-8 -*-
{
    'name': 'US Form 1099-NEC Summary',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Localizations',
    'summary': "Each contractor's 1099-NEC total for the year, the threshold check, and recipient statements",
    'description': """
US Form 1099-NEC Summary
========================

Builds on OCA's US Form 1099 (l10n_us_form_1099): for a tax year it totals
what was paid to each contractor marked as a 1099-NEC vendor, using sent,
completed payments only (OCA's own report counts every payment, including
drafts, cancelled and incoming ones), and leaves out payments through
journals marked as reported on Form 1099-K (card networks, payment apps).

It checks the filing threshold ($600 for payments up to 2025, $2,000 from
2026; later years can be set as system parameters), flags contractors
missing a taxpayer ID or address, and prints recipient statements
(Copy B) with the TIN masked.

Filing itself is done in the IRS's IRIS Taxpayer Portal, typing in the
figures this summary gives (or uploading IRIS's own CSV template).
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['l10n_us_form_1099'],
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'report/statement.xml',
    ],
    'installable': True,
    'application': False,
}
