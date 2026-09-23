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
- [`namecheap_domains/`](namecheap_domains/) - connects to Namecheap's
  reseller API to check domain availability and cache Namecheap's own
  per-TLD pricing marked up by a percentage, plus a `namecheap.domain`
  model tracking owned domains. Live-verified against a real Namecheap
  sandbox account - see
  [`namecheap_domains/README.md`](namecheap_domains/README.md) for what
  came out different from the docs (Namecheap's own pages block automated
  fetching, so this started from a third-party client's source instead).
- [`signalwire_voip/`](signalwire_voip/) - **Phase 1** of a SignalWire
  VoIP build: a core connector (project credentials, per-customer
  "subproject" provisioning, phone number search/purchase) for
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
  - [`signalwire_sms/`](signalwire_sms/) - **Phase 3**: two-way SMS -
    every message logs to the matched contact's chatter, with an
    optional per-number forwarding webhook into another system. Genuinely
    generic - a customer's own separate Odoo instance can install this
    directly to send/receive real SMS through whatever number(s) it has.
  - [`signalwire_voip_portal/`](signalwire_voip_portal/) - extends
    call routing out to the customer *portal*: an external contact can
    request a support callback (built), gated per-contact with room
    for tiers, structurally unable to ever reach an outside number -
    see its own README for the live browser-to-agent calling half,
    deliberately not yet built.
  - [`signalwire_voip_helpdesk_crm/`](signalwire_voip_helpdesk_crm/) -
    create or attach a helpdesk ticket, or create a CRM lead, straight
    from a voicemail - gated on whether the caller matched a known
    contact. Bridges to OCA's `helpdesk_mgmt` (Odoo's own `helpdesk`
    app is Enterprise-only) and core `crm`.
  - [`signalwire_voip_piper_tts/`](signalwire_voip_piper_tts/) -
    replaces the plain built-in voice on IVR menu and voicemail
    greetings with a self-hosted [Piper](https://github.com/OHF-Voice/piper1-gpl)
    TTS voice, scoped to two individually license-checked voices after
    catching that Piper's own example voice prohibits commercial use -
    see its README. Synthesis is eager (on save, never on a live call)
    with an always-on fallback to the plain voice; live-verified end to
    end against a real Piper server. LibriTTS-R's 904 speakers are
    selectable by real name/gender (sourced from the corpus's own
    published metadata, not curated), and a Preview button synthesizes
    typed sample text in the browser without placing a call.
  - [`signalwire_voip_project/`](signalwire_voip_project/) - create or
    attach a project task straight from a voicemail - gated on whether
    the caller matched a known contact, with a "fluid" lookup
    (Project/Task pickers narrowed to whatever's already flagged for
    that contact) and a smart default (exactly one matching project
    gets pre-filled on Create Task). Standalone - depends only on core
    `project`, not on `signalwire_voip_helpdesk_crm`.
- [`telehealth_booking/`](telehealth_booking/) - one field
  (`res.users.telehealth_video_tier`) and one hook point on
  `calendar.event` for a "premium video" upgrade path - installed
  alone, every booking just uses Odoo's own built-in Discuss video
  calling exactly as it already works. See its README for why that
  built-in calling has a real reliability ceiling worth knowing before
  promising it to paying patients (peer-to-peer WebRTC, no TURN relay
  configured by default).
- [`customer_deployment_checklists/`](customer_deployment_checklists/) -
  not an Odoo module, just plain CSV files for Odoo's own generic
  Project task import - one per service line (hosting, domains,
  SignalWire VoIP, SignalWire SMS, 10DLC registration, managed Odoo
  instance prerequisites) plus a universal onboarding one, re-used by
  hand for every new customer rather than re-derived from scratch each
  time.
- [`dms_onlyoffice/`](dms_onlyoffice/) - bridges ONLYOFFICE's own
  generic document-editing engine (`onlyoffice_odoo`) to OCA's
  Community-Edition-compatible `dms` module, filling the gap left by
  ONLYOFFICE's own ready-made bridge (`onlyoffice_odoo_documents`),
  which only works with Odoo's Enterprise-only `documents` app. A
  general-use connector, not tied to any one server - see its own
  README for the three real prerequisites and a scope limitation worth
  knowing before installing.
- [`project_task_partner_assignee/`](project_task_partner_assignee/) -
  one field, **Assigned Contact**, on `project.task` - Odoo core only
  lets a task's Assignees be internal staff (`user_ids`'s own domain
  excludes portal/share users); nothing in OCA's `project` repo covers
  contact-level task assignment either (checked both `18.0` and
  `19.0`). Auto-follows the assigned contact, mirroring how core's own
  Assignees already do, so the task's chatter can actually reach them
  by email - see its README for the one real access-shape nuance that
  comes with that.

**Meskis Works' own reselling/billing modules are private.** Everything
that exists purely to run Meskis' own reselling business - hosting and
domain storefronts, the SignalWire VoIP/SMS/10DLC storefront and
customer-token issuance, the unified subscriptions hub, and managed
Odoo instance deployment - moved 2026-09-16 to the private repo
`LadyHwesta/meskis-reseller-addons` (history preserved via
`git filter-repo`, not a fresh start). The dividing line: only a module
a customer would actually install on their own Odoo instance stays
here; anything that's Meskis' own proprietary pricing/provisioning/
customer-management logic doesn't. `signalwire_sms` itself was split
along that line - see its manifest for exactly what moved.

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
