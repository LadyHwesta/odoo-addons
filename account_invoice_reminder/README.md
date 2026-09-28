# Invoice Payment Reminders

A simple, multi-stage automatic reminder schedule for overdue customer
invoices - a handful of named stages, each a number of days before or
after an invoice's due date, each with its own email. A daily cron
sends whichever stage has come due for each unpaid invoice, once per
stage per invoice.

## Why this exists

OCA's own dunning module, `account_credit_control` (from the
`credit-control` repo), already exists for Odoo 19. It's a real,
capable tool, but it's a full dunning *engine* - policies, runs,
credit-control lines, communication channels - aimed at accounting
teams who need that much structure. It's also still Beta maturity and
licensed AGPL-3, unlike everything else in this repo (LGPL-3). The
lighter `account_invoice_overdue_reminder` module that used to cover
this simpler case was never ported past Odoo 18.

This module is the smaller alternative: one settings screen, four
ready-to-use stages out of the box, and nothing else to configure.

## What it does

- **Payment Reminders** (Invoicing/Accounting > Configuration): a list
  of stages, each with a `name`, a signed `days_offset` (negative =
  before the due date, zero = on the due date, positive = overdue),
  and an email template.
- Four stages ship installed and active: "3 Days Before Due" (-3),
  "Payment Due Today" (0), "Overdue Reminder" (+7), and "Final Notice"
  (+30) - each with a plain-language email template that gets firmer
  as the days go on. Install `mail_template_menu` (same repo)
  alongside this module to let a non-technical user tweak that wording
  without any Technical/developer-mode detour.
- A daily cron (`account.reminder.stage._cron_send_reminders`) checks
  every posted, unpaid customer invoice with a due date. A stage fires
  once elapsed days since the due date reach its `days_offset` -
  before/on-due-date stages fire only on their exact day (a "your
  invoice is due soon" notice sent after the fact would be confusing),
  overdue stages catch up if the cron run was ever delayed. Each stage
  only ever sends once per invoice (tracked on the invoice's own
  "Reminders Sent" field).
- A contact can be marked **"Exclude from Automatic Payment
  Reminders"** (on their Invoicing tab) to skip the schedule entirely
  - for board members, major donors, or any account someone would
  rather follow up with personally.
- Scoped per company from the start - a stage only applies to invoices
  in its own company.

## Setup

1. Install this module (and `mail_template_menu`, optional but
   recommended).
2. Review/edit the four default stages and their wording under
   **Invoicing/Accounting > Configuration > Payment Reminders**.
3. That's it - the daily cron is active out of the box.

## Known limitations

- Reminder emails are queued (`send_mail(..., force_send=False)`),
  the same pattern this repo already uses elsewhere
  (`club_equipment_loan`'s own overdue-reminder cron) - actual
  delivery depends on Odoo's own outgoing mail server setup and its
  periodic mail-queue cron. Not yet live-verified against a real mail
  server.
- No hold/pause per invoice beyond the partner-level exemption -
  there's no per-invoice "snooze this reminder" action.
- Vendor bills (`in_invoice`) are out of scope - this only reminds
  customers about money owed *to* this business, not the reverse.
