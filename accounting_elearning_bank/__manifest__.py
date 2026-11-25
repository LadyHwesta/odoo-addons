# -*- coding: utf-8 -*-
{
    'name': 'eLearning: Your Bank in Odoo',
    'version': '19.0.1.0.0',
    'category': 'Website/eLearning',
    'summary': "eLearning course on bank accounts in Odoo Community with OCA's statement import and "
               "reconciliation: set up right from day one, then reconcile every monthly statement",
    'description': """
eLearning: Your Bank in Odoo
============================

One course (Odoo's eLearning app), ready on install, with a quiz, for whoever
keeps the books:

* **How Odoo sees your bank**: the statement is the truth, and the holding
  accounts where money waits (Bank Suspense, Outstanding Receipts and
  Payments, Liquidity Transfer).
* **Set up from day one**: one bank journal per account, a savings account
  that tops up checking, your bank's CSV layout, automatic rules for the
  regulars, the owner's own money, and business names as branches.
* **When the statement arrives**: download and import, match line by line,
  prove the books match the bank, and what to look for when they don't.

Members only, by invitation, for invoicing users.
""",
    'author': 'Meskis Works',
    'website': 'https://meskis.net',
    'license': 'LGPL-3',
    'depends': [
        'website_slides', 'website_slides_publication_digest',
        'account_statement_import_sheet_file', 'account_reconcile_oca',
    ],
    'data': ['data/slide_channel_data.xml'],
    'assets': {
        'web.assets_frontend': ['accounting_elearning_bank/static/src/scss/course_content.scss'],
    },
    'installable': True,
}
