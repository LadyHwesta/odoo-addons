# Club Equipment Loans

Turns the Maintenance app's equipment register into a lending library for
club gear.

## What it adds

- **`is_loanable`** flag on `maintenance.equipment` to add an item to the
  pool. The equipment form then shows an **Availability** badge
  (available / reserved / on loan) and a **Loans** smart button; the
  equipment list gets *Loanable* and *Available to Loan* filters.
- **`club.equipment.loan`**: reference (`LOAN/<year>/nnnn`), borrower,
  loan officer, checked-out / due-back / returned dates, condition in and
  out, notes, chatter. States **reserved → out → returned** (or
  **cancelled**). A DB check keeps the due date on/after checkout; a
  Python guard keeps one active loan per item.
- **Workflow buttons**: Check Out (blocked until *Borrower Accepted
  Terms* is ticked), Check In (stamps the return date), Cancel, Reset,
  and **Print Agreement** (a QWeb PDF the borrower signs).
- **Overdue sweep** (cron, every 6h): `is_overdue` is a live computed flag
  that trips on the due date; a separate `overdue_notified` flag lets the
  sweep email the borrower and drop a To-Do on the loan officer exactly
  once per loan.
- **Portal**: *My Account → Equipment on loan* (`/my/loans`) lists what
  the logged-in member has out. A record rule limits portal users to
  their own loans; the page renders `sudo` so it can show the item name
  without granting portal users blanket equipment access.
- **Emails**: checkout confirmation (with the due date) and an overdue
  reminder, both editable `mail.template`s.
- **Menu**: Maintenance → Equipment Loans.

## Settings

**Settings → Equipment Loans → Default loan length** (days) pre-fills a new
loan's due date (`club_equipment_loan.default_days`, default 14).

## Requirements

Odoo 19 Community, `maintenance` + `mail` + `portal`. No extra Python
packages.

## Testing status

`tests/test_equipment_loan.py`:

- **TransactionCase** (12): reference + due-date defaults (incl. the
  setting); one active loan per item, and a freed item after return;
  checkout needs acceptance; full reserved→out→returned workflow with the
  return date; checkout queues the confirmation mail; the overdue sweep
  flags + notifies once and not again; equipment availability / current
  loan / count computes across the lifecycle; a non-loanable item has no
  availability; the due-before-checkout CHECK is enforced.
- **HttpCase** (1): a portal user sees their own loan on `/my/loans` and
  the "Equipment on loan" card on `/my`, without an AccessError.

The workflow buttons are covered via their model methods; they aren't
clicked through a browser in the suite. The loan-agreement PDF is wired
(report action + QWeb template) but not rendered in a test.
