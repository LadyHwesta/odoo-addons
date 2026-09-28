# -*- coding: utf-8 -*-
{
    'name': 'Invoice Payment Reminders',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'A simple multi-stage automatic email schedule for overdue customer invoices',
    'description': """
Invoice Payment Reminders
===========================

A lightweight, day-based reminder schedule for customer invoices - a
few named stages (e.g. "3 Days Before Due", "Overdue Reminder",
"Final Notice"), each keyed to a number of days before/after the due
date and its own email template. A daily cron sends whichever stage
is due for each unpaid invoice, once per stage per invoice.

OCA's own `account_credit_control` (from the `credit-control` repo)
already exists for Odoo 19, but it's a full dunning engine built
around policies, runs, and credit-control lines - more moving parts
and jargon than most small organizations need, it's still Beta
maturity, and it's AGPL-3 rather than this repo's usual LGPL-3. This
module is a deliberately smaller, single-purpose alternative: one
settings screen, four ready-to-use stages out of the box, nothing
else to configure.

See ``README.md`` for the full scheduling rules and what isn't
verified yet.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['account', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/mail_template_data.xml',
        'data/account_reminder_stage_data.xml',
        'data/ir_cron.xml',
        'views/account_reminder_stage_views.xml',
        'views/res_partner_views.xml',
        'views/account_move_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
}
