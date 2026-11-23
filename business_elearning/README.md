# eLearning: Basic Business Training

Two courses for a small business running Odoo, built into the eLearning app
on install (members only, by invitation), each with a quiz and screenshots
from a sample business ("Redwood Print Co."):

- **Customers and Sales** (everyone): My Day, the CRM pipeline, quotes
  customers sign and pay online.
- **Projects, Helpdesk and Your Website** (everyone): tasks for outside
  contacts, helpdesk tickets, the website and newsletter welcome email, login
  protection and app folders.

The accounting course, Getting Paid and Keeping the Books, is its own module
(`accounting_elearning`) so every suite can include it; this one depends on it.

The data file is built by `tools/build_course_data.py`: edit the lessons there
and rerun it when a screen changes. Screenshots are in `static/img`.
