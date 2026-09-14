# Odoo Addons

Custom Odoo 19 modules.

## Modules

- [`caldav_calendar/`](caldav_calendar/) - two-way calendar sync with any
  RFC 4791 CalDAV server (Nextcloud, Radicale, Baïkal, Fastmail, iCloud, ...).
- [`auth_imap/`](auth_imap/) - authenticate existing Odoo users against an
  IMAP mail server (mailbox password as a fallback login method).
- [`activitypub/`](activitypub/) - federate this Odoo instance into the
  Fediverse (Mastodon, Pleroma, Mobilizon, ...) over ActivityPub. The
  engine: actors, discovery, HTTP Signatures, delivery, inbox. Publishes no
  content on its own - install a bridge alongside it:
  - [`activitypub_website_blog/`](activitypub_website_blog/) - federate
    published blog posts.
  - [`activitypub_website_event/`](activitypub_website_event/) - federate
    published events.

  Start with [`activitypub/README.md`](activitypub/README.md); for a
  from-scratch setup against a real Fediverse server, follow
  [`TESTING_FEDERATION.md`](TESTING_FEDERATION.md) end to end.
- [`hestiacp_hosting/`](hestiacp_hosting/) - sell hosting packages through
  `website_sale`, bill them recurringly (via vendored OCA `contract`), and
  auto-provision/suspend/terminate the customer's account on a HestiaCP
  server as payment comes in, lapses, or the plan is cancelled. See
  [`hestiacp_hosting/README.md`](hestiacp_hosting/README.md) - in
  particular the "known simplifications" section (no portal page yet, no
  automatic saved-card renewal charge, and the HestiaCP API wire format
  itself hasn't been checked against a live server yet).

### Amateur radio club suite

A club-centric management setup on Odoo 19 **Community** (no Enterprise, no
paid apps). Install [`club_membership/`](club_membership/) to get the lot,
or pick pieces:

- [`club_membership/`](club_membership/) - the umbrella: a single **Club**
  app menu, an auto-rolling prorated *Annual Dues* product, and a
  `/my/club` member portal (dues, licence, gear, volunteering).
- [`club_amateur_radio/`](club_amateur_radio/) - call sign / FCC licence /
  ARRL fields on contacts, with one-click autofill from the FCC ULS
  (callook.info) and a licence-expiry sweep.
- [`club_equipment_loan/`](club_equipment_loan/) - a loaner library on top
  of the Maintenance app: checkout / return, due dates, overdue chasing, a
  printable agreement.

The suite also depends on **`event_volunteer`** (volunteer roles with slot
quotas on events, website sign-up, reminders), which now lives in
[`LadyHwesta/nonprofit-addons`](https://github.com/LadyHwesta/nonprofit-addons) -
it's deployment-neutral and shared with the non-profit work. Clone that
repo next to this one and add it to the addons path.

These also depend on four OCA membership modules vendored at the repo root
(`membership`, `website_membership`, `membership_prorate`,
`membership_withdrawal`) - Odoo 19 dropped the core Membership app and
OCA's proration / withdrawal add-ons aren't on a 19.0 channel yet. See
[`VENDORED.md`](VENDORED.md).

**eLearning training** - three small, pure-data modules that each drop
one ready-built course into Odoo's own **eLearning** app
(`website_slides`), one per functional area so a club only installs the
training that matches what it actually runs:

- [`club_elearning_membership/`](club_elearning_membership/) - *Membership
  Management* (dues/proration, the Club app, evacuation zones, reporting).
- [`club_elearning_amateur_radio/`](club_elearning_amateur_radio/) -
  *License & Callsign Tracking* (FCC lookup, the expiry sweep).
- [`club_elearning_equipment_loan/`](club_elearning_equipment_loan/) -
  *Equipment Loans* (the checkout/return workflow, overdue chasing).

Each is gated (`visibility="members"`, `enroll="invite"`) with the
matching security group auto-enrolled, and ends with a 4-question quiz.
See [`nonprofit-addons`](https://github.com/LadyHwesta/nonprofit-addons)'s
own README for the same pattern applied there, including a schema gotcha
worth knowing before adding another lesson: a `slide.slide`'s
`html_content` field needs real inline XML elements, not a
`<![CDATA[...]]>` block.

## Testing

[`testing/`](testing/) has a self-contained local Odoo 19 + Postgres
instance for trying these modules against a real server - see
[`testing/README.md`](testing/README.md).

## Compatibility & contributing

Everything here targets **Odoo 19.0** (see each module's `__manifest__.py`
- the `19.0.x.y.z` version already encodes that), tracked on `main`. That's
the version actively used and maintained.

Ports to other Odoo versions (e.g. 18.0) are welcome as PRs, but should
target a new version branch (e.g. `18.0`) rather than `main` - ask if that
branch doesn't exist yet and it'll get created. The expectation is that
whoever contributes a version port also owns keeping it compatible going
forward: reviews/merges happen here, but active maintenance of a
non-current-version branch isn't something to expect from the `main`
maintainer.

## License

LGPL-3 (see [`LICENSE`](LICENSE)), matching Odoo Community itself, unless a
module's own manifest says otherwise.
