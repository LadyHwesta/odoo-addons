# -*- coding: utf-8 -*-
{
    'name': 'Retained Earnings as Equity',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': "Accumulated Retained Earnings becomes an ordinary equity account, so the "
               "chart has one Current Year Earnings account and trial balances run",
    'author': 'Meskis Works',
    'website': 'https://meskis.net',
    'license': 'LGPL-3',
    'depends': ['account'],
    'post_init_hook': '_post_init_hook',
    'installable': True,
}
