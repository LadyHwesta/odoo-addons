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

From the user's avatar menu → **My Profile** (or Settings → Users for an
admin configuring someone else):

1. Fill in **CalDAV Server URL** (e.g. `https://cloud.example.com/`),
   **Username**, and **Password** — use an app-specific password if your
   server supports one (Nextcloud, Fastmail, iCloud all do).
2. Click **Discover Calendars** and pick the calendar to sync, *or* skip
   discovery and paste the full calendar collection URL directly into
   **Calendar URL**.
3. Click **Test Connection**, then **Sync Now** for an initial sync.
4. After that, the `CalDAV: Sync all active calendar accounts` scheduled
   action (Settings → Technical → Scheduled Actions, every 15 min by
   default) keeps it in sync automatically in both directions.

## How it works

- **Pull**: uses RFC 6578 `sync-collection` when the server supports it
  (incremental, cheap); falls back to a full `getctag` + listing compare
  otherwise.
- **Push**: `calendar.event` writes set a `need_caldav_sync` flag; the sync
  job `PUT`s dirty events with `If-Match`/`If-None-Match` ETag
  preconditions, and drains a small delete queue (`caldav.pending.delete`)
  for events removed in Odoo.
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
- One CalDAV calendar per Odoo user. Multiple calendars per user would need
  the `caldav_url` field to become a one2many.

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
- None of this has been run against a live Odoo + Postgres + real CalDAV
  server, since this machine only has the Odoo source checked out, not a
  runnable instance. The ORM orchestration (create/write/unlink overrides,
  `_apply_recurrence` calls, dirty-flagging, conflict handling) is verified
  by reading the source, not by executing it. Before relying on this for
  real calendars, run a real end-to-end pass: create a series, edit one
  occurrence, delete one occurrence, delete the whole series - both
  directions.

## Files

- `models/caldav_service.py` - plain-Python WebDAV/CalDAV client (no ORM,
  no Odoo import - unit-testable standalone).
- `models/res_users.py` - per-user account fields + sync orchestration
  (push/pull/conflict/recurrence-override handling) + cron entry point.
- `models/calendar_event.py` - `calendar.event` ↔ iCalendar field mapping
  (including RECURRENCE-ID overrides and EXDATE), dirty-tracking on
  write/unlink, the RECURRENCE-ID anchor (`caldav_recurrence_id_date`).
- `models/calendar_recurrence.py` - flags a series' master for push when
  the recurrence pattern itself changes (interval/count/until/weekdays),
  not just when the base event's own fields change.
- `models/caldav_pending_delete.py` - tombstone queue so deletes propagate
  even though the `calendar.event` row is already gone.
- `wizard/` - "Discover Calendars" picker.
