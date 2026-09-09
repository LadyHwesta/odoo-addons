# Event Volunteer Roles

Core Events lets people register to *attend*. This adds the other half a
club needs: signing up to *help run* an event.

## What it adds

- **Volunteer roles** on an event (`event.volunteer.role`): a name
  ("Net Control", "Setup Crew", "Talk-in Station"), a description, and how
  many people it needs. The event form gets a **Volunteers** tab with the
  roles, a live *signed-up / needed* count and an empty / partial / full /
  over-filled badge, plus a smart button to the full roster.
- **Assignments** (`event.volunteer.assignment`): who's doing what, with a
  Pending / Confirmed / Cancelled state, chatter, and a `note` for
  availability. Two guard rails, both skippable with
  `skip_volunteer_capacity` in context for a bulk fix-up:
  - one active sign-up per person per role;
  - a role can't be filled past its slot count (raise the count to add
    more).
- **Website sign-up**: the event page lists the roles with a *Volunteer*
  button; a full role shows "Role filled"; a member already on a role gets
  a *Withdraw* button. Public visitors get a "Sign in to volunteer" prompt
  and never see the roster.
- **Emails**: a confirmation on sign-up and a reminder a configurable
  number of days before the event (both `mail.template`s you can edit).
- Roles are copied when an event is duplicated; the roster is not.
- **Events → Volunteers** menu for the cross-event roster;
  **Configuration → Volunteer Roles** to manage them in bulk.

## Settings

**Settings → Events → Registration → Volunteer reminder lead time** —
days before an event that confirmed volunteers get the reminder
(`event_volunteer.reminder_lead_days`, default 2). The reminder cron runs
every 6 hours.

## Requirements

Odoo 19 Community, `event` + `website_event`. No extra Python packages.

## Testing status

`tests/test_event_volunteer.py`:

- **TransactionCase** (12): role counts and fill-state transitions;
  capacity blocks a third back-office sign-up and can be forced with
  context; no duplicate active sign-up; `action_portal_volunteer` /
  `action_portal_withdraw` happy paths incl. a freed seat being re-taken;
  portal sign-up refused when full; a confirmation email is queued on
  sign-up; the reminder cron sends once (inside the lead window, not
  outside) and doesn't re-send; event roll-up stats; roles copied on
  event duplication without the roster.
- **HttpCase** (1): a published event page renders the volunteer section
  for an anonymous visitor without an AccessError, showing the role and
  the sign-in prompt.

The POST sign-up / withdraw controller routes are thin wrappers over the
`action_portal_*` model methods (fully covered above); they aren't
exercised end-to-end through a browser POST (CSRF) in the test suite.
