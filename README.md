# Odoo Addons

Custom Odoo 19 modules.

## Modules

- [`base_technical_features/`](base_technical_features/) - vendored from OCA
  (see [`VENDORED.md`](VENDORED.md)): a "Technical feature" checkbox in user
  preferences gives permanent access to Settings > Technical menus (email
  templates, automated actions, ...) without ever needing developer mode.
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
  server as payment comes in, lapses, or the plan is cancelled. Includes a
  portal page, automatic saved-card renewal charging, a Hosting Service
  Agreement acceptance gate, and staff-driven package upgrade/downgrade
  (HestiaCP itself enforces downgrade safety). API calls verified live
  against a real HestiaCP server. See
  [`hestiacp_hosting/README.md`](hestiacp_hosting/README.md) - in
  particular "Known simplifications" (package *definitions* can't be
  managed via the API at all - only assigning an existing one to an
  account).
- [`namecheap_domains/`](namecheap_domains/) - connects to Namecheap's
  reseller API to check domain availability and cache Namecheap's own
  per-TLD pricing marked up by a percentage, plus a `namecheap.domain`
  model tracking owned domains. Live-verified against a real Namecheap
  sandbox account - see
  [`namecheap_domains/README.md`](namecheap_domains/README.md) for what
  came out different from the docs (Namecheap's own pages block automated
  fetching, so this started from a third-party client's source instead).
  - [`namecheap_hestiacp/`](namecheap_hestiacp/) - a small separate bridge
    module (install only if wanted) that can deploy an owned domain onto a
    `hestiacp_hosting` account: adds it as a web/DNS/mail domain there and
    points its nameservers at HestiaCP.
  - [`namecheap_domains_sale/`](namecheap_domains_sale/) - the public
    storefront: a `/domains` search-and-buy website page, real
    registration via `domains.create` on checkout, and yearly recurring
    renewal billing (vendored OCA `contract`) that actually calls
    `domains.renew` rather than just invoicing. Registration and renewal
    both live-verified end to end against the Namecheap sandbox.
- [`signalwire_voip/`](signalwire_voip/) - **Phase 1** of a SignalWire
  VoIP-reselling build: a core connector (project credentials, per-
  customer "subproject" provisioning, phone number search/purchase) for
  [SignalWire](https://signalwire.com/), a Twilio-API-compatible
  communications platform. Live-verified against a real trial account -
  see [`signalwire_voip/README.md`](signalwire_voip/README.md).
  - [`signalwire_voip_click2call/`](signalwire_voip_click2call/) -
    **Phase 2**: a real in-browser softphone, bridging vendored OCA
    `voip_oca` to SignalWire's SIP Endpoints - one click provisions a
    user's softphone, another routes an owned number's inbound calls to
    it. The SIP-over-WebSocket wiring is live-verified; actually placing
    or answering a call needs a human in a real browser, so that part is
    still to be done by hand. Also includes a real voicemail box
    (systray, playback, optional SignalWire transcription) and hardware
    desk phone support - each phone gets its own SIP Endpoint, rings
    alongside the softphone, and can be zero-touch auto-provisioned
    (Yealink/Grandstream) by MAC address; the underlying standard-SIP
    transport was live-verified, the auto-provisioning config files
    themselves are not yet tested against real hardware.
  - [`signalwire_sms/`](signalwire_sms/) - **Phase 3**: two-way SMS,
    both for the team's own use (every message logs to the matched
    contact's chatter) and for reselling - a customer gets
    independently-usable SignalWire API credentials plus a self-service
    portal page (`/my/sms`), with optional webhook forwarding into their
    own system.
    See its README for a live-confirmed gap (token revocation doesn't
    actually revoke). Live SMS testing was blocked by carrier-level
    10DLC compliance - see `signalwire_10dlc/` below, which now
    automates that registration.
  - [`signalwire_voip_sale/`](signalwire_voip_sale/) - **Phase 4**: the
    public storefront - a `/voip` search-and-buy page, real checkout-
    time provisioning (subproject, purchased number, an auto-issued
    customer SMS token), and **metered usage billing on real,
    itemized Call Detail Records**: a flat monthly number-rental line
    plus a second line priced by summing per-call/per-SMS CDRs (each
    individually marked up, so it carries a genuine customer-facing
    rate) - every metered invoice gets a proper itemized PDF phone
    bill attached, rather than folding usage into the invoice as one
    line per call. No new cron needed - hooks into the vendored
    `contract` module's own recurring-invoice cron.
  - [`signalwire_10dlc/`](signalwire_10dlc/) - self-service A2P 10DLC
    brand/campaign registration for resold customers - discovered the
    hard way that a real SMS send from an unregistered number gets
    rejected outright (`421717`). Confirmed live against the real
    account: brands/campaigns live flat at the top-level SignalWire
    account (no subaccount scoping exists at all), and a specific
    resold customer's number gets tied to their own campaign via an
    "order" - a path SignalWire's own docs don't document, found by
    reading real data back. A customer submits their own business
    details via a new `/my/sms/compliance` portal form (never the
    reseller's on their behalf) and opts in per number - never
    automatic at checkout, since only some customers will ever need
    SMS. Not live-tested with a real submission - that needs real
    customer business data and a real, non-refundable fee.
- [`telehealth_booking/`](telehealth_booking/) - one field
  (`res.users.telehealth_video_tier`) and one hook point on
  `calendar.event` for a "premium video" upgrade path - installed
  alone, every booking just uses Odoo's own built-in Discuss video
  calling exactly as it already works. See its README for why that
  built-in calling has a real reliability ceiling worth knowing before
  promising it to paying patients (peer-to-peer WebRTC, no TURN relay
  configured by default).
  - [`telehealth_booking_signalwire/`](telehealth_booking_signalwire/) -
    fills the hook in with real SignalWire Video: self-service upgrade,
    lazy per-provider subproject + metered billing provisioning (reusing
    `signalwire_voip_sale`'s own CDR/PDF-statement mechanism, extended to
    cover video room-session usage), and an Odoo-hosted join page
    embedding a vendored copy of SignalWire's browser SDK. The room/
    token layer is live-verified end to end through the real Odoo
    models; per-participant usage billing is not, since generating that
    data needs an actual joined WebRTC call.
- [`reseller_subscriptions/`](reseller_subscriptions/) - one unified
  self-service "My Subscriptions" portal page across hosting, domains,
  and SignalWire telecom, instead of three separate (or, for domains
  and SignalWire, nonexistent) portal experiences. Closes a real
  billing gap along the way: SignalWire numbers never had their
  contract linked back to them, so nothing ever auto-charged a
  SignalWire customer's saved card, and releasing a number never
  stopped billing for it - both fixed here. Also adds a "stop
  renewing" action for domains, which had none before. Deliberately
  doesn't touch `hestiacp_hosting`/`namecheap_domains_sale`'s own
  already-live billing code - see its README for the full design and
  a real gap it surfaces but doesn't fix in this pass
  (`hestiacp.account.action_terminate()` has the same billing-doesn't-
  actually-stop bug `action_release()` had).
- [`managed_odoo_instances/`](managed_odoo_instances/) - Phase 2:
  treats "we run a dedicated Odoo instance for you" as a real,
  billable product - shared multi-tenant server for smaller
  customers, or a dedicated VPS for anyone who needs their own. The
  actual system-level work (nginx vhost, SSL via certbot, database
  creation + app install) is done by a small standalone companion
  service in its own separate repo,
  [`meskis-deploy-agent`](https://github.com/LadyHwesta/meskis-deploy-agent) -
  this module only ever calls it over HTTPS with a bearer token, the
  same client pattern as everywhere else in this repo; it never holds
  SSH credentials. Requesting an instance generates a real
  `project.project` deployment checklist - for a brand-new dedicated
  server, including the one-time bootstrap script as a task
  attachment (sent to Tiesa to run by hand, never the customer).
  Bills through `reseller_subscriptions`'s own
  `contract.billing.mixin`, but only starts invoicing once an instance
  is actually marked live. Optionally automates the one prerequisite
  the bootstrap script can't - creating a dedicated VPS in the first
  place - via UpCloud's real API (`upcloud.account`), **live-verified
  2026-09-15**: a real server was created, confirmed reachable over
  SSH with an injected key, then destroyed. Sellable as a normal
  Sales-app quote - a "hosting tier" product (shared/dedicated)
  creates the instance on order confirmation, bundling in whatever
  `deployment.app` products are on the same order; no public
  storefront, since the customer's actual domain isn't known from an
  order alone - it schedules an activity for the salesperson to
  confirm that and click Request themselves. See its README for what's
  still a deliberate manual step (the X-Odoo-Dbfilter routing middleware
  itself, deeper per-instance configuration) and
  `meskis-deploy-agent`'s own README for what's not yet live-verified
  (the bootstrap script itself, against a real server).
- [`customer_deployment_checklists/`](customer_deployment_checklists/) -
  not an Odoo module, just plain CSV files for Odoo's own generic
  Project task import - one per service line (hosting, domains,
  SignalWire VoIP, SignalWire SMS, 10DLC registration, managed Odoo
  instance prerequisites) plus a universal onboarding one, re-used by
  hand for every new customer rather than re-derived from scratch each
  time.

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
