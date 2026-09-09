# -*- coding: utf-8 -*-
{
    'name': 'Club Equipment Loans',
    'version': '19.0.1.0.0',
    'category': 'Association',
    'summary': 'Lend club gear to members: checkout / return, due dates, '
               'overdue chasing, and a printable loan agreement',
    'description': """
Club Equipment Loans
====================

Turns the Maintenance app's equipment register into a lending library.

* Flag a piece of equipment as **loanable** to add it to the pool.
* A **loan** records who has it, when it's due back, and its condition out
  and in. States: reserved -> out -> returned (or cancelled). Only one
  active loan per item.
* A member has to accept the loan terms before it can be checked out; the
  **loan agreement** prints as a PDF.
* A scheduled action flags loans past their due date, emails the borrower,
  and puts a To-Do on the loan officer.
* Members see **what they have out** in the website portal (My Account ->
  Equipment on loan).

Requires `maintenance`. No extra Python packages.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['maintenance', 'mail', 'portal'],
    'data': [
        'security/ir.model.access.csv',
        'security/club_equipment_loan_security.xml',
        'data/ir_sequence_data.xml',
        'data/mail_template_data.xml',
        'data/ir_cron.xml',
        'report/equipment_loan_report.xml',
        'views/club_equipment_loan_views.xml',
        'views/maintenance_equipment_views.xml',
        'views/res_config_settings_views.xml',
        'views/equipment_loan_portal_templates.xml',
    ],
    'installable': True,
    'application': False,
}
