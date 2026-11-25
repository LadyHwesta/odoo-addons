# -*- coding: utf-8 -*-
{
    'name': 'eLearning: Getting Paid and Keeping the Books',
    'version': '19.0.1.0.1',
    'category': 'Website/eLearning',
    'summary': "eLearning course on accounting in Odoo Community with OCA's accounting apps: "
               "reminders, statements, bank import and reconciliation, reports, lock dates",
    'description': """
eLearning: Getting Paid and Keeping the Books
=============================================

One course (Odoo's eLearning app), ready on install, with a quiz, for whoever
sends invoices and keeps the books:

* **Getting paid**: payment reminders and customer statements.
* **The bank**: importing a bank statement file and reconciling it.
* **Reports and closing**: the trial balance and other financial reports,
  fiscal years and lock dates, assets and repeating entries.

Members only, by invitation, for invoicing users.
""",
    'author': 'Meskis Works',
    'website': 'https://meskis.net',
    'license': 'LGPL-3',
    'depends': [
        'website_slides', 'account_invoice_payment_reminder', 'mail_template_menu', 'partner_statement',
        'account_statement_import_sheet_file', 'account_reconcile_oca', 'account_financial_report',
        'account_tax_balance', 'account_fiscal_year', 'account_lock_date_update',
        'account_asset_management', 'account_move_template',
    ],
    'data': ['data/slide_channel_data.xml'],
    'assets': {
        'web.assets_frontend': ['accounting_elearning/static/src/scss/course_content.scss'],
    },
    'installable': True,
}
