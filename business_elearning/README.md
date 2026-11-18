# eLearning: Basic Business Training

Three courses for a small business running Odoo, built into the eLearning app
on install (members only, by invitation), each with a quiz and screenshots
from a sample business ("Redwood Print Co."):

- **Customers and Sales** (everyone): My Day, the CRM pipeline, quotes
  customers sign and pay online.
- **Getting Paid and Keeping the Books** (invoicing users): payment
  reminders, customer statements, importing a bank statement file,
  reconciling, the trial balance and other financial reports, fiscal years and
  lock dates, assets and journal entry templates.
- **Projects, Helpdesk and Your Website** (everyone): tasks for outside
  contacts, helpdesk tickets, the website and newsletter welcome email, login
  protection and app folders.

The accounting lessons cover the OCA accounting modules (financial reports,
partner statements, statement import, reconciliation, fiscal years, lock dates,
assets, move templates) on Odoo Community.

The data file is built by `tools/build_course_data.py`: edit the lessons there
and rerun it when a screen changes. Screenshots are in `static/img`.
