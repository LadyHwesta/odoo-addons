# Amateur Radio Club

The umbrella module for the club suite. Install this and it pulls in
everything else; it also adds the bits that only make sense once the whole
suite is present.

## What it pulls in

| Module | For |
| --- | --- |
| `membership` (OCA, vendored) | the member register |
| `membership_prorate` (OCA, vendored) | calendar-year dues, prorated for mid-year joiners |
| `membership_withdrawal` (OCA, vendored) | resignation reason + date |
| `website_membership` (OCA, vendored) | opt-in public member directory |
| [`club_amateur_radio`](../club_amateur_radio/) | call sign / FCC licence / ARRL, with autofill |
| [`event_volunteer`](../event_volunteer/) | volunteer roles + website sign-up |
| [`club_equipment_loan`](../club_equipment_loan/) | loaner equipment library |

## What it adds

- **A single Club app menu** gathering Members, Events, Volunteers,
  Equipment Loans and the configuration screens, so the day-to-day club
  work is in one place instead of spread across the Membership, Events and
  Maintenance apps. Those apps stay installed and reachable - this is an
  extra front door, not a replacement.
- **An "Annual Club Dues" product** - membership, prorate on, priced 25.00
  (change it), dated to the current calendar year. A daily cron
  (`_cron_roll_membership_year`) moves any prorated, expired membership
  product into the new year on/after 1 January, so proration keeps
  charging new members the right fraction without anyone editing dates
  every January. Plain (non-prorate) membership products are left alone.
- **`/my/club`** - a member portal home with dues status, licence class +
  expiry (with a "Renew soon" badge inside the warning window), evacuation
  zone, equipment currently out, and upcoming volunteer commitments; plus a
  card for it on the portal home whose counter is "things needing
  attention" (licence expiring + overdue loans).
- **Evacuation zones** - a `club.evacuation.zone` model (name, code,
  coordinator) and an `evacuation_zone_id` field on every contact, on the
  Membership page. Manage zones under Club > Configuration.
- **Reporting** (Club > Reporting):
  - **Member Roster** - a list of members with call sign, licence class +
    expiry, membership status + renewal date, evacuation zone and contact
    details; filter and group by any of those (default group: zone).
    **Print > Member Roster** gives a PDF of whatever's filtered/selected.
  - **Event Statistics** - `report.club.event`, a per-event analysis
    (attendees, volunteers signed up vs slots needed, unfilled slots,
    understaffed roles) as graph / pivot / list, e.g. attendance by month.
  - **Volunteer Participation** - confirmed volunteer assignments across
    all events as a pivot (by member to see who turns out, by role to see
    what's hard to fill).
  - **Members Analysis** - OCA `membership`'s own membership/revenue report.

## Requirements

Odoo 19 Community. Everything is core or vendored at the repo root (the
four OCA `membership*` modules - see [`VENDORED.md`](../VENDORED.md)); no
extra Python packages, nothing extra on the addons path.

## Testing status

`tests/test_club_membership.py`:

- **TransactionCase**: the Annual Dues product is installed with prorate on
  and this-year dates; the Club menu tree exists; the New Year cron rolls
  an expired prorated product forward and leaves a plain membership product
  untouched; an evacuation zone's `member_count` computes and its `code` is
  unique; the Member Roster PDF renders with a member's name and call sign;
  `report.club.event` returns the right attendee / volunteer / shortfall /
  understaffed counts for an event; the reporting actions and menu exist.
- **HttpCase**: a portal member with a call sign, an out loan and a
  confirmed future volunteer slot loads `/my/club` (200) and sees their
  call sign, the equipment, the event and the "Renew soon" licence badge;
  the "My Club" card shows on `/my`; and the compiled `web.assets_web.css`
  carries no SCSS error (guards the repo layout).

Green on a fresh install of the whole suite (48 tests across the six
modules). Views / menus / the roster PDF aren't clicked through a browser
beyond the checks above.
