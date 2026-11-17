# My Day

A start screen to plan and work through the day, built 2026-11-17 as a first
version for review.

## What's on it

**Plan the day** (left):

- **Today's schedule**: your calendar events today, all-day first. What's on
  now is marked, and online meetings have a **Join** button.
- **To-dos**: your activities that are overdue or due today, with **Done**
  (marks the activity done, as from the chatter) and a count of the rest of
  the week.
- **Phone** (with the SignalWire VoIP click-to-call module): unread
  voicemails for you and your call groups, with the start of the transcript,
  **Call back** and **Heard**; and callbacks waiting for you (asked for you or
  your group, or claimed by you), with **Call back** (dials through your
  softphone and marks it done) and **Done**. Clicking a callback opens what
  it's about (set by the receptionist on the callback), else the contact.

**Needs attention** (right), each only if the app is installed and you may
see it:

- **Helpdesk tickets** (OCA Helpdesk): your open tickets, priority first,
  with the SLA deadline when Helpdesk SLA is installed, and how many are
  unassigned in your teams.

- **Tasks due**: your open tasks with a deadline this week or already past.
- **Money** (for people who handle invoices): overdue customer invoices and
  vendor bills due within a week, as an amount and count **per company**.
- **Quotes waiting on customers**: your sent quotes, by expiry date.
- **Events this week**: events, plus booked gigs when Gig Bookings
  (`sale_gig_booking`) is installed.

Click anything to open it; each section has a link to its full list.

## Companies and branches

It follows the company switcher: with several companies or branches
selected, it shows them all and puts a company badge on each item and on
each money line. The companies are buttons at the top (branches marked):
tap one to see only it, tap others to add them, and tap the last one again
to see all. Your choice is remembered in this browser.

## Start screen

Tick **Start on My Day** in **Preferences** to open it after login. An
administrator can set it for anyone on the user's form (Preferences tab).
It sets Odoo's own Home Action for the user.

## Adding a section

Extend `my.day._my_day_sections()` with `(column, key)` and add a method
`_my_day_section_<key>(today)` returning a dict (`title`, `icon`, `count`,
`items`, `empty`, optionally `note` and `more`), or `None` when it doesn't
apply. Items come from `_my_day_item()`; give them `buttons` made with
`_my_day_button()` (run a method, then remove the item, dial the number it
returns, or reload) and a `record` to open when it isn't the item itself. Run it with the user's own rights, within `self.env.companies`.
