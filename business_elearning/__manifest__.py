# -*- coding: utf-8 -*-
{
    'name': 'eLearning: Basic Business Training',
    'version': '19.0.1.0.0',
    'category': 'Website/eLearning',
    'summary': "eLearning courses for a small business on Odoo: sales, getting paid and the books, "
               "projects, helpdesk and the website",
    'description': """
eLearning: Basic Business Training
==================================

Three short courses (Odoo's eLearning app), ready on install, each with a quiz:

* **Customers and Sales**: My Day, the CRM pipeline, and quotes customers
  sign and pay online.
* **Getting Paid and Keeping the Books**: payment reminders, customer
  statements, importing and reconciling bank statements, the trial balance and
  other reports, fiscal years, lock dates, assets and repeating entries.
* **Projects, Helpdesk and Your Website**: tasks for outside contacts,
  helpdesk tickets, the website and newsletter, login protection and app folders.

Members only, by invitation: everyone for the first and third, invoicing
users for the second.
""",
    'author': 'Meskis Works',
    'website': 'https://meskis.net',
    'license': 'LGPL-3',
    'depends': [
        'website_slides', 'crm', 'sale_management', 'helpdesk_mgmt', 'my_day',
        'account_invoice_payment_reminder', 'mail_template_menu', 'partner_statement',
        'account_statement_import_sheet_file', 'account_reconcile_oca', 'account_financial_report',
        'account_tax_balance', 'account_fiscal_year', 'account_lock_date_update',
        'account_asset_management', 'account_move_template', 'project_task_partner_assignee',
        'mailing_list_welcome', 'security_auth_guard', 'web_app_drawer_folders',
    ],
    'data': ['data/slide_channel_data.xml'],
    'assets': {
        'web.assets_frontend': ['business_elearning/static/src/scss/course_content.scss'],
    },
    'installable': True,
}
