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
- **Texts** (with the SignalWire SMS module): texts to the business's own
  numbers waiting for an answer, yours and the unassigned ones, with
  **Take**, **Reply** (opens the reply form, from the number it came in
  on) and **Done**. A text to a number that rings one person is assigned
  to that person; texts to call-group or menu numbers stay unassigned.
  Sent texts and the STOP/START/HELP replies the system answers itself
  count as handled.

**Needs attention** (right), each only if the app is installed and you may
see it:

- **Threat status** (with Login Protection, `security_auth_guard`), for
  security officers only: a green / amber / red status in words, counts of
  new critical and warning events, blocked addresses and this week's
  automatic blocks, and the events that need attention, critical first,
  with **Reviewed**. Blocks that worked (Info events) are only counted,
  never listed.
- **Helpdesk tickets** (OCA Helpdesk): your open tickets, priority first,
  with the SLA deadline when Helpdesk SLA is installed, and how many are
  unassigned in your teams.

- **Leads** (CRM): your open leads and opportunities in the pipeline's
  working stages (not archived or lost, not won, not in a folded stage),
  those with a next
  step overdue or due first (date in red when late), with the contact,
  stage and expected revenue; then the newest unassigned leads in your
  sales teams, with **Take**, and how many are waiting.
- **Tasks due**: your open tasks with a deadline this week or already past.
- **Money** (for people who handle invoices): overdue customer invoices and
  vendor bills due within a week, as an amount and count **per company**.
- **Quotes waiting on customers**: your sent quotes, by expiry date.
- **Events this week**: events, plus booked gigs when Gig Bookings
  (`sale_gig_booking`) is installed.

Click anything to open it; each section has a link to its full list.

## Colour and backgrounds

Each section has its own colour (icon, header tint, count). Sections other
modules add get one too, or set their own with a `color` key.

The picture button at the top picks a background: none, one of six
built-in scenes (drawn by `tools/make_backgrounds.py`), or your own photo.
The choice is per user (also in Preferences); on a picture the page sits on
frosted panels so it stays readable.

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

## Choose your own sections

Everyone sets up their own My Day: the sliders button at the top of My Day
(or **My Preferences → My Day**) lists every section they're allowed to see.
For each one they choose:

- **Show**: hide a section they don't need.
- **Order**: drag the rows.
- **Column**: Plan the day (left) or Needs attention (right).
- **Items**: how many it lists (1-30; the schedule defaults to 30, to-dos to 24, the rest to 8).
- **Days**, on some sections: how far ahead to look (to-dos: also list what's due in the next N days,
  default 0; tasks, bills and events: default 7).
- **Team**, on some sections: include call groups' voicemails and callbacks, texts nobody has taken,
  new unassigned leads, or the count of unassigned tickets in your teams (default on).

A section someone loses access to drops off their list and keeps their choices for when it comes back.
People only ever change their own rows, and only these options (`my.day.section.setting`; Preferences
save with elevated rights, so the model enforces this itself, not record rules alone). Administrators
can see and change everyone's.

## Adding a section

Extend `my.day._my_day_sections()` with `(column, key)` and add a method
`_my_day_section_<key>(today)` returning a dict (`title`, `icon`, `count`,
`items`, `empty`, optionally `note` and `more`), or `None` when it doesn't
apply. Items come from `_my_day_item()`; give them `buttons` made with
`_my_day_button()` (run a method, then remove the item, dial the number it
returns, or reload) and a `record` to open when it isn't the item itself. Run it with the user's own rights, within `self.env.companies`.

The person's choices apply to it automatically (show, order, column). For the
item count use `self._my_day_limit('<key>')`; to offer **Days** or **Team**,
extend `_my_day_section_options()` with `{'<key>': {'days': (default, label)}}`
or `'team'`, and read them with `_my_day_days()` / `_my_day_team()`.
