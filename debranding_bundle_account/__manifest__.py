# -*- coding: utf-8 -*-
{
    'name': 'Debranding Bundle: Accounting',
    'version': '19.0.1.0.0',
    'category': 'Hidden/Tools',
    'summary': "Plain names for the bank statement import and financial reports: "
               "no project names in the menus and buttons",
    'author': 'Meskis Works',
    'website': 'https://meskis.net',
    'license': 'LGPL-3',
    'depends': ['debranding_bundle', 'account_financial_report', 'account_statement_import_file'],
    'data': ['views/labels.xml'],
    # Installs itself when the bundle, the financial reports and the
    # statement import are all there.
    'auto_install': ['debranding_bundle', 'account_financial_report', 'account_statement_import_file'],
    'installable': True,
}
