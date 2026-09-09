# Amateur Radio Club - Member Profiles

Adds the amateur-radio facts a club keeps on its members to every Odoo
contact, and fills them in for you from the FCC.

## What it adds

On the contact form, an **Amateur Radio** tab:

- **Call sign** (stored uppercased), **FRN**, **operator class**
  (Technician … Amateur Extra), **licence type** (individual / club
  station / …), licence **grant** and **expiry** dates, Maidenhead **grid
  square**.
- For a club-station licence, its **trustee** (name + call sign).
- An **ARRL member** flag.
- **Licence last checked** and a computed **Licence expiring soon** flag.

Call sign and expiry are also columns (optional) on the Contacts list, and
the Contacts search gets *Licensed*, *Licence Expiring Soon*, *ARRL Member*
filters plus a group-by *Operator Class*.

## Call-sign lookup

**Look up call sign** on the contact form queries
[`callook.info`](https://callook.info) — a free, no-key JSON wrapper around
the FCC Universal Licensing System (US amateur licences; call-sign data is
public record) — and fills:

- every licence field above, always (the FCC is authoritative);
- the contact **name** and **mailing address**, only when they're still
  blank, so a lookup on a brand-new member is one click but a lookup on an
  existing one never clobbers what you typed.

A daily scheduled action (**Amateur Radio: refresh FCC licences**) re-checks
every member with a call sign, refreshes the expiry date, and raises one
*To-Do* activity per member whose licence has expired or expires within the
warning window. It pauses briefly between calls to be kind to callook.info,
and a single bad call sign never stops the sweep.

## Settings

**Settings → Amateur Radio Club**:

- **FCC call-sign lookup** — turn the whole thing off for an air-gapped
  install; the fields stay editable by hand.
- **Licence expiry warning window** — days before expiry that a licence
  counts as "expiring soon" (default 60).

The callook.info base URL is overridable via the
`club_amateur_radio.callook_base_url` system parameter (used by the tests to
point at a stub).

## Requirements

Odoo 19 Community, `contacts` + `mail`. Only `requests` (already bundled
with Odoo) — no extra Python packages, no API key.

## Testing status

`tests/test_uls_lookup.py` covers the callook.info response parsing
(individual and club payloads, name/address splitting, date formats), the
`lookup()` guard rails (blank / invalid / disabled / network error all
raise a clean `UserError`), the form button (fills blanks, keeps an
existing name, uppercases the call sign), the expiring-soon compute
(including already-expired), and the nightly cron (refreshes licence data,
raises exactly one expiry To-Do and doesn't duplicate it, skips entirely
when disabled). The HTTP layer is mocked throughout — no test makes a real
network call. Not yet exercised against the live callook.info service from
a running instance.
