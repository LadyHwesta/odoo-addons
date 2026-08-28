# CalDAV Calendar Sync

Two-way sync between Odoo's Calendar app and any RFC 4791 CalDAV server
(Nextcloud, Radicale, Baïkal, Fastmail, iCloud, ...), the same way core
`google_calendar` syncs with Google.

No extra pip packages: it only uses `requests`, `lxml`, `vobject` -
all already core Odoo dependencies.

## Install

1. Copy this folder into your addons path (or symlink it):
   `ln -s ~/Documents/odoo-addons/caldav_calendar /path/to/your/addons/caldav_calendar`
2. Restart Odoo with `--update caldav_calendar` (or install from Apps).

## Setup (per user)

Each user can add any number of CalDAV calendar accounts - each syncs
independently, with its own credentials and sync cursor. From the user's
avatar menu → **My Profile**, the "CalDAV Calendar Sync" section shows a
read-only summary of their accounts; **Manage CalDAV Calendars** opens the
real list/form to add or edit one:

1. **New**, give it a **Name** (just a label, e.g. "Personal" or "Work").
2. Fill in **CalDAV Server URL**, **Username**, and **Password** — use an
   app-specific password if your server supports one (Nextcloud, Fastmail,
   iCloud all do).
3. Save, then click **Discover Calendars** and pick the calendar to sync,
   *or* skip discovery and paste the full calendar collection URL directly
   into **Calendar URL**.
4. Click **Test Connection**, then **Sync Now** for an initial sync.
5. After that, the `CalDAV: Sync all active calendar accounts` scheduled
   action (Settings → Technical → Scheduled Actions, every 15 min by
   default) keeps every account in sync automatically in both directions.

**Which calendar does a new event sync to?** If you have exactly one
writable account, new events sync to it automatically - the same "just
works" behavior as when this module only supported one calendar. With two
or more accounts there's no way to guess which one a new event belongs to,
so it's created unsynced; pick one from the **Sync to CalDAV Calendar**
field on the event itself (only shows writable calendars belonging to that
event's organizer).

**Read-only subscriptions.** Tick **Read-Only Subscription** on an account
for calendars you can only view, not change - subscribed holiday feeds,
team calendars you lack write access to, ICS subscriptions. Odoo still
pulls remote changes for these on every sync, but never pushes: local
edits to those events stay local, deletes aren't propagated, and the
account is skipped by both new-event auto-assignment and the **Sync to
CalDAV Calendar** picker. This keeps a view-only calendar from
accumulating `need_caldav_sync` flags and delete tombstones for writes the
server would just reject (and from flipping the account to `error` when it
does). Untick it later and normal two-way push resumes.

## How it works

- **Pull**: uses RFC 6578 `sync-collection` when the server supports it
  (incremental, cheap); falls back to a full `getctag` + listing compare
  otherwise.
- **Push**: `calendar.event` writes set a `need_caldav_sync` flag; the sync
  job `PUT`s dirty events with `If-Match`/`If-None-Match` ETag
  preconditions, and drains a small delete queue (`caldav.pending.delete`)
  for events removed in Odoo. Accounts flagged **Read-Only Subscription**
  skip this phase entirely - they only ever pull.
- **Conflicts**: last-write-wins, remote takes priority when both sides
  changed the same event between syncs (logged, not silently discarded -
  check `caldav_last_sync_error` / server logs if this matters to you).

## Recurring events and per-occurrence exceptions

Recurring events sync their `RRULE` in both directions and are properly
expanded into the full series of `calendar.event` occurrences (pulling a
remote RRULE calls the same `_apply_recurrence()`/`_apply_recurrence_values()`
primitives Odoo's own recurrence engine uses - just writing the `rrule`
field is not enough, it only updates the structured fields, not the
occurrence rows). Deleting the master resource remotely cascades to the
whole local series via `_caldav_unlink_events()`, not just the base event.

**Per-occurrence exceptions are supported**, matching RFC 5545 §3.8.5.3: a
recurring series is one CalDAV resource holding a master VEVENT (RRULE +
EXDATE) plus one extra VEVENT per modified occurrence, each carrying a
`RECURRENCE-ID`.

- A moved/retitled/rescheduled single occurrence pulled from the server
  becomes a `calendar.event` row with `follow_recurrence=False`, matched
  across syncs by `caldav_recurrence_id_date` - a stable anchor (the
  occurrence's *original* per-RRULE slot time) stamped once when the row is
  first created and never touched again, so re-matching still works even
  after the occurrence has been moved more than once.
- A single occurrence deleted on the server (`EXDATE`) deletes just that one
  local row, not the series.
- Editing one occurrence in Odoo (any of name/description/location/start/
  stop/attendees, not just start/stop the way core Odoo's own UI heuristic
  does) marks it `follow_recurrence=False` and flags the series' master for
  push; the next push serializes it as its own `RECURRENCE-ID` VEVENT.
- Deleting one occurrence in Odoo (a plain row delete - Odoo has no EXDATE
  concept internally) flags the master for push; the next push computes a
  fresh `EXDATE` by diffing the RRULE's expected slots against the rows that
  still exist.

**Recurrence edge cases, by design, not oversights:**
- If a whole series' RRULE genuinely changes (not just re-applied
  unchanged), Odoo's own reconciliation may detach exceptions whose moved
  time no longer fits the new pattern - into standalone non-recurring
  events, not deleted. This is native Odoo behavior for a full-pattern edit,
  not something this module works around.
- `calendar.recurrence.dtstart` is `min()` of all occurrence starts, so an
  exception moved to *before* the series' original start can, in principle,
  skew Odoo's own occurrence-range math. The EXDATE builder sidesteps this
  by anchoring on the master event's own `start` rather than
  `recurrence.dtstart`, but it's a pre-existing characteristic of Odoo's
  recurrence engine worth knowing about if dates look off in that scenario.

## Known limitations

- Alarms/reminders are not synced.
- Attendees are matched/created by e-mail only; no invite e-mails are sent
  by this module (Odoo's own calendar notifications still apply locally).
- Each `calendar.event` syncs through at most one `caldav.account`. There's
  no way to mirror the same event into two different calendars.

## Upgrading from a v1 install (one calendar per user)

19.0.2.0.0 replaced the flat `caldav_*` fields on `res.users` with a
`caldav.account` model (one2many from the user), so a user can have
several calendars instead of exactly one. `migrations/19.0.2.0.0/
post-migrate.py` handles this automatically on `-u caldav_calendar`: for
any user with the old fields configured, it creates one `caldav.account`
carrying over their URL/credentials/sync state, and repoints their
already-synced `calendar.event` rows at it. Verified against a real
upgrade (seeded old-schema data, ran the upgrade, confirmed the new
account and the event's new `caldav_account_id` both came out right, and
that Odoo dropped the old columns cleanly afterward) - not just read
against the migration script.

## Testing status

- Field names, view anchors, and the recurrence engine's call graph
  (`_apply_recurrence`, `_apply_recurrence_values`, `_get_occurrences`,
  `_inverse_rrule`, `SELF_READABLE_FIELDS`/`SELF_WRITEABLE_FIELDS` as
  overridable `@property`s, the `other_preferences` view slot, ...) were
  checked against the real Odoo 19.0 source (`~/dev/odoo-19`, `odoo/odoo`
  branch `19.0`), not recalled from memory.
- The ics build/parse logic (single events, RRULE, and the master+override+
  EXDATE multi-VEVENT shape, both timed and all-day) is covered by
  standalone round-trip tests against the real `vobject`/`lxml`/`requests`
  packages, independent of Odoo.
- Verified end-to-end against a real Odoo 19 + Postgres instance talking to
  a real CalDAV server (OwnCloud/SabreDAV): connect, discover calendars,
  push a plain event, push a recurring series, move+retitle one occurrence,
  delete one occurrence, delete a whole series, and the reverse - an
  external client creating/editing/deleting events that Odoo then pulls in.
  Each push was independently re-fetched with a raw client and re-parsed to
  confirm the server's own stored copy (not just what was sent) round-trips
  correctly. This caught one real bug: `_caldav_pull` was skipping straight
  to the inefficient full-listing fallback whenever there was no stored
  sync-token yet, instead of first trying `sync_collection(None)` - a valid
  RFC 6578 bootstrap request that returns the full listing *and* a fresh
  token in one round-trip. Fixed; confirmed the incremental path now
  actually engages on a compliant server.
- **Read-only subscriptions (19.0.2.1.0) are not yet verified end-to-end.**
  The change is small and mechanical - every code path that would set
  `need_caldav_sync`, enqueue a `caldav.pending.delete`, or auto-assign a
  new event now also checks `caldav_account_id.read_only`, and
  `_caldav_sync` skips `_caldav_push` for such accounts - but it hasn't
  been exercised against a real read-only calendar yet.
- Multi-account support (a previous version) verified via `odoo-bin shell`: a
  user with one account still auto-syncs new events to it (unchanged
  behavior); adding a second stops the auto-assignment and each account's
  push query only ever picks up its own events, never the other's; the
  `ir.rule` genuinely hides one user's accounts from another. Also
  screenshotted the real rendered UI (Playwright + headless Chromium) for
  both the Preferences summary list and the full account list/form, not
  just reasoned about the view XML.

## Files

- `models/caldav_service.py` - plain-Python WebDAV/CalDAV client (no ORM,
  no Odoo import - unit-testable standalone).
- `models/caldav_account.py` - one CalDAV calendar subscription: its own
  credentials, sync cursor, and all sync orchestration (push/pull/conflict/
  recurrence-override handling) + the cron entry point. A user can have
  several.
- `models/res_users.py` - just the `caldav_account_ids` one2many for the
  self-service Preferences summary.
- `models/calendar_event.py` - `calendar.event` ↔ iCalendar field mapping
  (including RECURRENCE-ID overrides and EXDATE), dirty-tracking on
  write/unlink, the RECURRENCE-ID anchor (`caldav_recurrence_id_date`), and
  auto-assigning a new event to its organizer's one account when they only
  have one.
- `models/calendar_recurrence.py` - flags a series' master for push when
  the recurrence pattern itself changes (interval/count/until/weekdays),
  not just when the base event's own fields change.
- `models/caldav_pending_delete.py` - tombstone queue so deletes propagate
  even though the `calendar.event` row is already gone.
- `migrations/19.0.2.0.0/post-migrate.py` - carries old single-account
  data forward into the new model on upgrade.
- `wizard/` - "Discover Calendars" picker.
