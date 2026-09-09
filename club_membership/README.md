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
  expiry (with a "Renew soon" badge inside the warning window), equipment
  currently out, and upcoming volunteer commitments; plus a card for it on
  the portal home whose counter is "things needing attention" (licence
  expiring + overdue loans).

## Requirements

Odoo 19 Community. Everything is core or vendored at the repo root (the
four OCA `membership*` modules - see [`VENDORED.md`](../VENDORED.md)); no
extra Python packages, nothing extra on the addons path.

## Testing status

`tests/test_club_membership.py`:

- **TransactionCase** (3): the Annual Dues product is installed with
  prorate on and this-year dates; the Club menu tree exists; the New Year
  cron rolls an expired prorated product forward and leaves a plain
  membership product untouched.
- **HttpCase** (1): a portal member with a call sign, an out loan and a
  confirmed future volunteer slot loads `/my/club` (200) and sees their
  call sign, the equipment, the event and the "Renew soon" licence badge;
  the "My Club" card shows on `/my`.

Green on a fresh install of the whole suite (43 tests across the six
modules). The unified Club menu and the portal page aren't clicked through
a browser beyond the checks above.
