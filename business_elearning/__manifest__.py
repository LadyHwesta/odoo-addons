# -*- coding: utf-8 -*-
{
    'name': 'eLearning: Basic Business Training',
    'version': '19.0.1.0.0',
    'category': 'Website/eLearning',
    'summary': "eLearning courses for a small business on Odoo: sales, projects, helpdesk and "
               "the website, plus the accounting course",
    'description': """
eLearning: Basic Business Training
==================================

Two short courses (Odoo's eLearning app), ready on install, each with a quiz,
plus the accounting course from ``accounting_elearning``:

* **Customers and Sales**: My Day, the CRM pipeline, and quotes customers
  sign and pay online.
* **Projects, Helpdesk and Your Website**: tasks for outside contacts,
  helpdesk tickets, the website and newsletter, login protection and app folders.

Members only, by invitation, for everyone.
""",
    'author': 'Meskis Works',
    'website': 'https://meskis.net',
    'license': 'LGPL-3',
    'depends': [
        'website_slides', 'accounting_elearning', 'crm', 'sale_management', 'helpdesk_mgmt', 'my_day',
        'project_task_partner_assignee',
        'mailing_list_welcome', 'security_auth_guard', 'web_app_drawer_folders',
    ],
    'data': ['data/slide_channel_data.xml'],
    'assets': {
        'web.assets_frontend': ['business_elearning/static/src/scss/course_content.scss'],
    },
    'installable': True,
}
