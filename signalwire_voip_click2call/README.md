# SignalWire Click-to-Call

Phase 2 of the SignalWire VoIP project (see
[`signalwire_voip`](../signalwire_voip/)'s own README for Phase 1).
Bridges OCA's [`voip_oca`](../voip_oca/) - a free, provider-agnostic
SIP.js/WebRTC browser softphone for Odoo 19 - to SignalWire.

## Why this exists instead of a simpler REST call-bridging approach

The original plan (before `voip_oca` was found via the standard
"check OCA first" pass) was a simpler REST-only click-to-call: click
Dial, SignalWire calls your real phone, then bridges to the contact -
no browser audio needed, but no receiving calls inside Odoo either.
`voip_oca` already provides a complete in-browser softphone (make AND
receive calls, click-to-call from any partner, call log, missed-call
activities), and SignalWire's SIP Endpoints plug into it directly -
this got a much more capable result for a smaller build, once found.

## Setup

1. Have a `signalwire.server` already configured (see `signalwire_voip`),
   **and its SIP Domain field filled in** - copy the real value from
   this project's SignalWire dashboard, SIP Profile page
   (`https://<space>.signalwire.com/sip_profile/edit`). This is **not**
   the same as the Space domain with `.sip.` inserted - see "The SIP
   domain gotcha" below for why that distinction matters.
   `pip install phonenumbers` into the Odoo server's own Python
   environment too - see "Calling a contact whose number has no
   country code" below for why this is required, not optional, for
   outbound calls to actually connect.
2. On that server's form, click **Setup Click-to-Call** - creates the
   one `voip.pbx` record every user's softphone shares (idempotent,
   safe to click again if the server's SIP Domain ever changes).
3. On each user who should get a softphone (their own user form,
   Preferences or the admin Users list, VOIP tab): click
   **Provision SignalWire Softphone** - creates a real SIP Endpoint at
   SignalWire and fills in `voip_oca`'s own `voip_pbx_id`/
   `voip_username`/`voip_password` fields. That's the whole setup -
   the user now has a working softphone (outbound calling + click-to-
   call from any partner) the moment they open Odoo.
4. To let a purchased `signalwire.phone_number` **receive** calls into
   someone's softphone: set its **Rings** field to that user, then
   click **Configure Inbound Routing**. Requires `web.base.url` to
   already be this database's real, public HTTPS address - SignalWire
   has to be able to reach it to deliver the inbound-call webhook.

## Call Groups and business-hours routing

A `signalwire.phone_number`'s **Rings** field can point at either a
single user (as above) or a **Call Group** (`signalwire.call.group`) -
a named, reusable list of members whose softphones (and desk phones)
all ring at once. Distinct from a personal **Also Ring** list a user
sets up for their own fallback chain (see the voicemail section below)
- a Call Group is a shared record other numbers, or an IVR menu
option once that exists, can point at too, not something tied to one
person's own settings.

If a Call Group's own call goes unanswered, it falls through to
whichever user's **Unanswered Calls Go To** field is set on the group
itself (their own voicemail box) - or just a spoken apology if that's
left blank, since a group has no single natural owner for a full
personal fallback chain the way a directly-routed user gets.

Optionally set a **Business Hours** calendar (a real `resource.
calendar` record - the same thing HR/attendance uses to define a
weekly schedule and holidays) on a number, plus an **After-Hours**
route - a call arriving outside those hours uses the after-hours
target instead of the regular one, checked live on every call via
`resource.calendar`'s own working-interval API rather than a
hand-rolled day/time comparison. Leave the calendar blank for a
number that should always route the same way regardless of time.

A number's **Rings** field can also be set to **An IVR Menu**
(`signalwire.ivr.menu`) - a caller-facing "Press 1 for Sales" menu.
Each menu has a spoken greeting (text-to-speech, no audio upload in
v1) and a list of single-digit options, each either ringing a user,
ringing a Call Group, jumping into another menu, taking a voicemail,
or hanging up. An unrecognized digit re-prompts the same menu rather
than rejecting the call outright.

### Multi-company

A single SignalWire account (one `signalwire.server`/subproject setup)
can serve every company in a multi-company database - each
`signalwire.phone_number` has its own `company_id`, and every routing
target (assigned user, Call Group, IVR Menu, and their after-hours
equivalents) is constrained to that same company via Odoo's own
`check_company` mechanism (`_check_company_auto = True` on the models
involved - `check_company=True` alone does nothing without this,
confirmed by reading `_check_company_auto`'s own real effect in
Odoo 19's `orm/models.py` rather than assuming). A Call Group's own
members and an IVR Menu option's own targets are checked the same
way, so a number belonging to Branch A can never be configured to
accidentally ring Branch B's own people. `res.users`'s own
`_check_company_domain` override compares against a user's real
`company_ids` (multi-company membership), not a single `company_id`,
so a user genuinely shared across companies isn't incorrectly
excluded.

## The SIP domain gotcha - a real bug this project shipped, then fixed

**`_get_sip_domain()` used to *guess* the SIP domain** from the Space
domain (`{space-name}.sip.signalwire.com`) rather than requiring it be
configured directly. That guess looked solid at every layer available
from a terminal: it accepted a real WebSocket upgrade
(`101 Switching Protocols` / `Server: SignalWire Proxy`), and a raw SIP
REGISTER against it over UDP got back a genuine `401 Unauthorized` /
`WWW-Authenticate: Digest` challenge rather than a connection failure -
both looked like confirmation the domain was right.

It wasn't. Every real registration attempt against that guessed domain
failed with `401 Unauthorized`, even after independently recomputing
the SIP digest hash by hand (MD5, matching byte-for-byte against the
client's own `response=` value) proved the credentials themselves were
cryptographically correct. SignalWire support's own answer (2026-09-20,
after live troubleshooting against the user's real space): the actual
SIP domain carries an additional hidden, space-specific suffix beyond
the space name (e.g. `yourspace-4bfcc2d4e531.sip.signalwire.com`, not
just `yourspace.sip.signalwire.com`) - visible only on the dashboard's
own SIP Profile page, not derivable from the space name and not
returned by the SIP Endpoint creation API response either.

**Fixed 2026-09-20**: `_get_sip_domain()` no longer guesses anything -
`signalwire.server` now has its own **SIP Domain** field, and the
method raises a clear error if it isn't set rather than silently
producing a plausible-but-wrong value again. Every existing server
record (including the user's real production one) needs this field
filled in from the dashboard before softphones/desk phones will
actually register.

## Calling a contact whose number has no country code

Once the SIP domain gotcha above was fixed and inbound calling worked,
outbound calling from a contact still just sat at a dialtone.
`voip_oca`'s own dial logic
(`voip_agent_service.esm.js`'s `call()`) strips a phone number down to
bare digits and dials exactly that - it never adds a country code. A
contact entered as `(707) 555-0123` (no `+1`) dials as 10 bare digits,
which SignalWire's SIP trunk just waits on rather than routing
anywhere - not a SignalWire bug, a number that was never
fully-qualified to begin with.

**Fixed without touching `voip_oca`'s own vendored code**: `res.partner.
format_partner()` (the one method both the softphone's Partner tab and
call-history redial already go through) is overridden here to run the
phone number through core's own `_phone_format(force_format='E164')`,
which derives the country code from the contact's own `country_id`
(falling back to the company's) - so a contact's phone field can stay
exactly as entered, no need to re-enter every number with a country
code by hand. A second small JS patch routes the phone-widget "click
to call" icon on a contact's own form/list (the more common way to
call a contact, separate from the softphone's Partner tab) through the
same fixed method.

**A real, non-obvious prerequisite**: this only works if the
`phonenumbers` Python library is installed in the Odoo server's own
environment - it is **not** part of Odoo's own `requirements.txt`,
confirmed by checking core's actual file. Without it, `_phone_format`
degrades silently (Odoo core's own designed behavior for this optional
dependency) rather than raising - the fix would appear to do nothing
at all, with no error anywhere, and calling would still just sit at a
dialtone. Caught exactly this way while testing this fix: `pip install
phonenumbers` was missing from the local test venv, and the new test
below failed until it was added. **`pip install phonenumbers` into the
real Odoo server's environment is required**, not optional, for this
fix to actually take effect there.

Covers dialing sourced from a `res.partner` record specifically (the
softphone's own Partner tab, call-history redial, and the phone-widget
click on a contact's form/list). A phone-widget click on a *different*
model with a phone field (a lead, for instance) still dials the raw
digits unchanged - out of scope here since it wasn't the reported
problem, flagged rather than silently left implicit.

## Outbound calls still failing after all of the above: no TURN server

Even with the correct SIP domain and a correctly country-coded number,
outbound-to-PSTN calls from a contact still just sat at a dialtone
forever. Live SIP tracing (DevTools WS frames during a real call
attempt) narrowed this down precisely, in order:

1. The INVITE itself was correct (right number, right domain) and got
   a `100 Trying` back from SignalWire - so the call route was being
   accepted.
2. It then sat forever with no further response - traced to the SIP
   Credential's own **Call Handler** setting on SignalWire's dashboard
   defaulting to *not* allowing outbound PSTN dialing at all (a
   distinct, explicit "Passthrough (Allow dialing to PSTN)" option
   exists and must be selected - "Use Default Setting" isn't it).
3. With that fixed, the INVITE completed but the call still failed
   with a real SIP `480 Temporarily Unavailable` /
   `Reason: cause=804 "MEDIA_TIMEOUT"` - the call route was accepted
   but the actual RTP media path between the browser and SignalWire's
   gateway never connected.

Root cause of step 3: `voip_oca` only ever configures SIP.js's default
STUN server (`stun.l.google.com`) - no TURN relay anywhere in
`voip_oca` or this module. A failing INVITE's own SDP confirmed it:
only host/server-reflexive (STUN-derived) candidates were ever
offered, never a relay candidate. STUN alone isn't always enough to
establish a real media path - that's specifically what TURN exists
for, and SignalWire's own docs don't advertise a TURN service for
third-party SIP.js integrators (checked directly).

**Fixed** by standing up a real TURN server and wiring the softphone
to fetch short-lived credentials for it:

- **coturn was tried first and abandoned** - a confirmed, long-
  standing upstream bug (`438 Wrong nonce`, reported against coturn
  since 2017 across many versions, both its `lt-cred-mech` and
  `use-auth-secret` auth modes) made it reject its own just-issued
  nonce on literally the first authenticated request of a fresh
  process. Not a config mistake on our end - independently reproduced
  and matched to open, unresolved upstream GitHub issues.
- **[eturnal](https://eturnal.net/)** (an actively maintained,
  Erlang-based STUN/TURN server) was used instead - no compatibility
  issue, confirmed working via a standalone ICE test
  (`https://webrtc.github.io/samples/src/content/peerconnection/trickle-ice/`)
  before ever wiring it into Odoo. No `.deb` package exists for it;
  built from source (`erlang` + `libyaml-dev` + `build-essential` are
  the real build dependencies - the source tarball bundles its own
  `rebar3`), installed to `/opt/eturnal`, running under the official
  systemd unit template from eturnal's own repo.
- `signalwire.server` gained `turn_host`/`turn_secret` fields (System
  group only). `_generate_turn_credentials()` derives a short-lived,
  HMAC-SHA1 TURN REST API credential per call (the same scheme both
  coturn and eturnal implement) - `turn_secret` itself never reaches
  the browser, only the time-limited derived pair, fetched by
  `res.users.get_signalwire_turn_credentials()` (callable by any
  softphone user via `sudo()`, since only the safe derived value is
  ever returned) and wired into SIP.js's ICE config by
  `voip_agent_turn.esm.js`, patched onto `voip_oca`'s own `call()`.

**A second real bug found deploying this**: the first version of this
patch fetched the TURN credential once, when the softphone first
connected, and cached it for the page's lifetime. A softphone can stay
connected in an open browser tab far longer than a short-lived
credential's TTL - live testing confirmed exactly this: the SDP
correctly offered relay candidates, but eturnal's own log showed
`Rejecting request: credentials expired` the moment a call was placed
more than the TTL after the page loaded. Fixed by fetching a fresh
credential on every `call()` instead of once at connect time, and
mutating the live `UserAgent`'s own `configuration.
sessionDescriptionHandlerFactoryOptions` directly rather than only
setting it once at `UserAgent` construction - confirmed by reading
SIP.js's own source that each new call's session description handler
reads that config fresh at setup time, so no `UserAgent`
reconstruction is needed to pick up a new credential.

**A third real bug, found on the very next live test**: with the
credential-expiry bug fixed, the SDP *still* had no relay candidate at
all - yet eturnal's own log showed the TURN allocation succeeding
(both UDP and TCP), just a moment too late, and later reported
`Relayed 0 KiB` when the unused allocation was torn down. Root cause:
SIP.js's own default ICE gathering timeout is 5000ms (confirmed by
reading its source), and a full TURN Allocate handshake
(unauthenticated request -> 401 challenge -> authenticated retry, for
both UDP and TCP transports) doesn't reliably finish inside that
window - SIP.js sends whatever's gathered so far the moment gathering
finishes *or* that timeout fires, whichever comes first, and there's
no mechanism to trickle a late-arriving candidate into an
already-sent SIP INVITE afterward. Fixed by setting
`iceGatheringTimeout: 10000` in the same `sessionDescriptionHandlerFactoryOptions`
object as the ICE servers themselves - a sibling key, not nested under
`peerConnectionConfiguration`.

**Live-verified 2026-09-20**: the TURN server itself (a real `relay`
candidate obtained against it via a standalone ICE test, independent
of Odoo), a real outbound call's SDP correctly offering relay
candidates sourced from a freshly-fetched, correctly-scoped backend
credential, and (separately) the credential-expiry and gathering-
timeout bugs each caught by an actual live call attempt failing in a
new, specific way after the previous fix.

### The actual root cause, found 2026-09-22 via SignalWire support + a packet capture

Every fix above was correct but not sufficient - outbound calls still
MEDIA_TIMEOUT'd. Escalated to SignalWire support with a real Call SID/
timestamp and a `tcpdump` capture of one failing attempt (captured on
the TURN server itself, not filtered to port 5060 - this project's
softphone signaling runs over encrypted WSS, not raw SIP, so that
filter caught nothing on a first attempt). Reading the capture without
`tshark` still showed something concrete: our own TURN relay completed
a clean allocation and stayed healthy throughout (sub-200ms round
trips, steady keepalives), while SignalWire's media server sent 30
STUN connectivity-check probes to each of two relay candidate ports,
once a second for the full 30-second call, and got zero response back.

SignalWire support confirmed the mechanism from that same capture:
they deliver their SDP answer in the **183 Session Progress**, a
provisional response - and **SIP.js only applies an answer carried in
a provisional response when the `Inviter` is constructed with
`earlyMedia: true`**, which defaults to `false`. Without it, the
answer is never applied, the ICE agent never receives SignalWire's
candidates to pair against, never installs a `CreatePermission` for
SignalWire's media address on our own TURN relay, and our relay
correctly (per RFC 8656 9.4) silently drops every connectivity check
from a peer with no installed permission - which is exactly the STUN-
requests-with-no-response pattern the capture showed. The call then
runs out SignalWire's own 30-second DTLS timer and fails with the
480/`cause=804 MEDIA_TIMEOUT` seen throughout this whole saga. None of
the TURN/STUN/gathering-timeout work above was wrong - the relay truly
is healthy - it just never got a chance to do anything, because the
browser never knew where to send a permission request to.

**First fix attempt**: `earlyMedia` is only settable via the `Inviter`
constructor's own options, with no shared/UserAgent-level default
(confirmed by reading `voip_oca`'s vendored `sip.js`), so - per this
project's standing rule against hand-editing `voip_oca` itself - the
fix was a new patch, `voip_agent_early_media.esm.js`, fully
reimplementing `VoipAgent.call()` with the one changed line
(`{earlyMedia: true}` on the `Inviter`). 164 tests green, deployed to
the branch, but genuinely not yet live-tested at the time.

### A second bug, found live-testing the first fix: `earlyMedia: true` connects, then immediately hangs up

The first fix worked exactly as diagnosed - the call now genuinely
connects. But right at answer, SIP.js itself tears it down with a
client-generated 488, logging:

```
"Early media dialog does not equal confirmed dialog, terminating session"
```

That message is SIP.js's own "this INVITE forked" guard - the whole
reason `earlyMedia` needs it is that a WebRTC offer can't be forked
(RFC-level limitation, not a SIP.js choice). Sent SignalWire the exact
SIP trace; their engineer's own server-side analysis proved the dialog
**never changed** - identical Call-ID/To-tag/From-tag, byte-identical
SDP (down to the ICE credentials and DTLS fingerprint) on both the 183
and the 200 OK. They also confirmed the `earlyMedia` fix itself
worked correctly on their end: ICE selected a real candidate pair,
DTLS completed, SRTP was flowing both directions - this call was
never actually a fork. They suspected their 183 being *unreliable*
(no `100rel`/`RSeq` - our INVITE doesn't request it) might be
confusing SIP.js's own internal tracking, and asked for the SIP.js
debug log naming the exact check that fired.

Captured it (Odoo developer mode ties directly into `voip_oca`'s own
SIP.js log level - no separate config needed) and read
`onProgress`/`onAccept` directly in the vendored `sip.js` to find the
real mechanism: `onProgress` (handling the 183) sets
`this.earlyMediaDialog = session`, where `session` is a *per-response*
wrapper object (`inviteResponse.session`). `onAccept` (handling the
200 OK) later compares `this.earlyMediaDialog !== session` by plain
JS reference equality against a **different** per-response wrapper
for the exact same real dialog - confirmed independently on our own
side too, since our client's own `sip.invite-dialog` logger tracks a
single persistent dialog object (same id string) from `constructed` at
the 183 straight through to the ACK/BYE we send ourselves. Both
wrappers represent the identical SIP dialog; they're just different JS
object instances. The check is comparing the wrong thing - a genuine
SIP.js library defect, not fixable upstream (last release 0.21.2,
October 2022 - our exact vendored version; no newer release exists,
no matching public issue found either).

**The actual fix**: `Session.setAnswer()` (`sip.js:2330`) operates on
`this` (the `Inviter` instance itself, which persists for the whole
call) and its own lazily-created `SessionDescriptionHandler` - never
on the buggy per-response `session` wrapper at all. So the real work
that establishes ICE/DTLS doesn't need SIP.js's own `earlyMedia`
machinery in the first place. Rewrote `voip_agent_early_media.esm.js`
entirely: every `Inviter` now stays at SIP.js's own default
(`earlyMedia: false`, so `earlyMediaDialog` is never assigned and
`onAccept`'s buggy branch is structurally unreachable - `onAccept`
itself needed **zero** changes), and a new patch on
`SIP.Inviter.prototype.onProgress` calls `this.setAnswer(answer,
options)` directly the moment a provisional response carries a
matching SDP answer - the same call SIP.js's own `earlyMedia` path
would have made, just without ever touching `earlyMediaDialog`. When
the real 200 OK arrives, stock `onAccept` reapplies its own answer via
that same unmodified `setAnswer()` call it already makes today -
harmless and idempotent here, since SignalWire's SDP is byte-identical
between the 183 and the 200 OK. `voip_agent_attended_transfer.esm.js`
went back to a plain `new SIP.Inviter(...)` with no options, since the
new prototype patch covers every `Inviter` constructed anywhere.

One real sequencing gotcha found while implementing this: `sip.js`
isn't part of `voip_oca`'s regular asset bundle - it's a separate lazy
bundle (`voip_oca.agent_assets`) loaded inside
`VoipAgent.connectAgent()`, so the global `SIP` object doesn't exist
at page load. The `SIP.Inviter.prototype` patch has to be applied from
inside a `connectAgent()` patch instead (after confirming `SIP` is
actually loaded, since `connectAgent()` itself returns early without
loading it in several cases - non-prod mode, no RTC support, missing
PBX config), guarded so reconnecting never stacks duplicate patches
onto the same shared prototype.

191 tests still green. **Not yet live-tested** - this is genuinely the
next real call attempt to make, now grounded in the actual confirmed
bug rather than a guess.

## Live-verified 2026-09-15, against the user's real trial account

- **A real phone number was purchased** (`+12084449665`, into a new
  "Internal Team" subproject representing the business's own
  resources rather than a resold customer) specifically to test this
  phase - the first real trial-credit spend in this project, done with
  the user's explicit go-ahead.
- **SIP Endpoint creation** (`action_provision_signalwire_sip`) reuses
  the already-live-tested `POST /api/relay/rest/endpoints/sip` call
  from Phase 1 - not re-tested with a live call here, but the
  underlying API call itself was already proven to work.
- `voip_oca`'s own JS builds the SIP URI as
  `sip:{voip_username}@{voip_pbx domain}` (confirmed by reading its
  source, `voip_agent_service.esm.js`) - this is exactly what
  `_get_sip_domain()` + the SIP Endpoint's `username` field produce
  together, so no translation layer was needed between the two.

## What's NOT live-verified - and can't be, from here

**Actually placing or receiving a call.** Everything above proves the
*wiring* is correct (the right hostname, the right SIP URI shape, the
right webhook contract), but confirming a real call actually connects
and carries audio needs a human in a real browser with a microphone -
that's the one thing that can't be driven from a terminal. **Once
`web.base.url` points at this database's real public address**, the
concrete next step is: log in as a provisioned user, open the
softphone widget (top bar), and either dial out or have someone call
one of the numbers configured to ring that user.

## The inbound call webhook

`POST /signalwire/voice/inbound` - one URL serves every purchased
number (looked up by the call's `To` field against
`signalwire.phone_number`, rather than a unique callback URL per
number). Returns standard Twilio-compatible cXML:

- Assigned user has a softphone: `<Dial timeout="20" action="...">
  <Sip>sip:{username}@{sip domain}</Sip></Dial>` - bridges the inbound
  call to their browser softphone, with a fallback chain (see below)
  taking over if it isn't answered in time.
- No matching number, or no assigned/provisioned user: `<Reject/>` -
  declines cleanly rather than leaving the caller in silence.

This exact mechanism (`<Dial><Sip>`) is standard, well-documented
Twilio/SignalWire Compatibility API behavior - unlike the SIP/WSS
hostname above, it didn't need live discovery, just implementing
correctly. The controller itself IS tested (`HttpCase`, real HTTP
round trip against the local test server) - what's untested is
SignalWire actually reaching it, which needs the database to be
publicly addressable first.

## If nobody's at the softphone: the fallback chain

**SignalWire has no presence/registration API at all** - confirmed
2026-09-15, searching specifically for one. There's no way to ask "is
this SIP Endpoint currently online" before dialing it. The only real
mechanism is a timeout on the dial attempt, then reacting to how it
ended - so that's what this is: `<Dial timeout="20" action="...">`,
and the `action` callback decides what happens next based on
`DialCallStatus`.

Three independently-toggleable steps, self-service (a user's own
Preferences, not an admin setting), each skipped if not configured:

1. **Forward to a saved number** (`signalwire_active_forward_id`) -
   picked from a small personal address book
   (`signalwire.forwarding.number`, one user can save several: cell,
   home, ...) rather than a single field to retype. A **Use My Profile
   Phone** button seeds one straight from the user's own partner
   record, per the original ask to use "phone info stored in the
   user's Odoo account."
2. **Ring a group** (`signalwire_ring_group_ids`) - every teammate in
   the list who has their own SIP Endpoint provisioned gets rung *at
   the same time* (not one-by-one) - the field's own domain hides
   teammates without a softphone, since ringing one would just fail
   immediately anyway.
3. **Voicemail** (`signalwire_voicemail_enabled`, on by default) - the
   guaranteed last resort so a caller is never just dropped. Recording
   gets downloaded and stored as a real `ir.attachment` (not just a
   link to SignalWire's own hosting), attached to the matched
   contact's chatter if one was found (same digits-only matching
   approach as `signalwire_sms`'s own, duplicated here rather than
   shared since this module doesn't depend on that one), and **always**
   schedules a "return this call" activity for the intended agent
   regardless of whether a contact was matched.

All three can be active at once - the chain tries them in that fixed
order (softphone -> forward -> group -> voicemail), skipping whichever
aren't configured, so a user who's only turned on voicemail goes
straight there instead of stalling on an empty forward/group step.

**Not live-verified**: the fallback chain's own webhook logic IS
tested end to end (`HttpCase`, every transition, every skip-if-
unconfigured case), and the voicemail recording fetch is tested
against a mocked HTTP response - but nothing here has been exercised
against a real SignalWire call yet, same category of gap as the base
inbound webhook above.

## The voicemail box itself: systray, playback, and transcription

Voicemail wasn't meant to just be a chatter message and an activity -
the follow-up ask was a real voicemail box: a quick way to check it
from the backend, and (if possible) a transcript so a user can decide
whether a recording is worth listening to in full.

- **A topbar systray icon** (microphone glyph, unread-count badge)
  whose dropdown lists recent unread voicemail - caller, duration,
  transcript snippet once one's ready, and an inline player - without
  leaving whatever screen you're on. It updates **instantly**, not on
  a timer: the server pings the user's own bus channel
  (`user._bus_send('signalwire_voicemail/updated', {})`, the same
  mechanism core's own `mail.activity` systray badge already relies on
  for its live count) whenever a voicemail is created, its
  read/unread state changes, or its transcript lands.
- **A full Voicemail list/form** (existing menu, unchanged location) -
  inline HTML5 playback, transcript display, Mark Read/Unread buttons,
  a "My Voicemails, Unread first" default filter. Pressing play marks
  a voicemail read automatically (same convention as most mail/
  voicemail clients: opening and listening implies "seen").
- **Genuine self-service ownership, not just a read-only inbox**: an
  `ir.rule` scopes a plain user to their own voicemail records with
  real read/write/unlink - they can mark read/unread and delete
  without any admin involvement. `signalwire.voicemail.system`
  (managers) still sees and can manage everyone's.
- **Transcription** is SignalWire's own Compatibility API feature
  (`<Record transcribe="true" transcribeCallback="...">`, confirmed
  against SignalWire's own docs - not yet live-verified end to end
  against an actual spoken voicemail, since that needs a real call).
  It's a paid add-on on SignalWire's end, billed per recording, so
  it's **on by default but a one-click, per-user toggle**
  (`signalwire_voicemail_transcribe`) right next to the voicemail
  setting itself - turning it off only ever gets the audio.
  `transcribeCallback` fires asynchronously, well after the call has
  ended, and its payload carries `RecordingUrl` but neither our own
  `user_id`/`phone_number_id` nor a `CallSid` (confirmed against
  SignalWire's docs) - so `RecordingUrl`, stored on the voicemail
  record the moment the recording itself completes, is what
  correlates that later webhook back to the right row. Once a
  transcript lands: it's posted to chatter (same places the original
  voicemail notice went) and folded into the still-open "return this
  call" activity's own note, so a user scanning the Activities
  systray sees the transcript without opening anything at all.

## Custom greetings, message length/beep, and call-group shared mailboxes

Every mailbox used to play the same hardcoded greeting with the same
fixed 120s cap and beep always on. Self-service now, next to the
existing voicemail toggle on a user's own Preferences:

- **A custom greeting** - either a real uploaded audio file
  (`signalwire_voicemail_greeting`, a plain Odoo file upload, played
  via `<Play>`) or, if none is set, editable text-to-speech
  (`signalwire_voicemail_greeting_text`, via `<Say>`, same convention
  the IVR menu greeting already uses). **Deliberately file-upload
  only, not in-browser mic recording** - a meaningfully bigger JS lift
  nobody explicitly asked for; record it however you like (phone voice
  memo, etc.) and upload the file.
- **Max message length** (`signalwire_voicemail_max_length`, seconds)
  and **beep on/off** (`signalwire_voicemail_beep`), both self-service.
- SignalWire fetches an uploaded greeting from a new public route,
  `/signalwire/voice/greeting/<attachment_id>` - unauthenticated by
  necessity (SignalWire's own media server fetches `<Play>` URLs
  directly, same reason `/signalwire/voice/inbound` itself is public),
  but scoped to attachments actually currently set as somebody's own
  greeting rather than an open-ended attachment-id fetch - same
  accepted-risk shape as this module's own desk-phone auto-
  provisioning route.

**Call groups can now have their own shared voicemail box**, not just
route to one member's personal one. `signalwire.call.group.
voicemail_mode` picks between ending the call, a specific member's own
box, or the group's own shared mailbox. A group mailbox posts to the
**group's own chatter** (any member can see and manage it there, or
via the Voicemail list's own "My Groups' Voicemails" filter, granted
by a new `ir.rule` scoping group members to their own groups' shared
records) - **deliberately no per-member "return this call" activity**
the way a personal voicemail gets, since a group has no single natural
owner for that (same reasoning already given for why a group has no
full personal fallback chain). A group mailbox also deliberately uses
the same generic default greeting/length/beep a personal mailbox falls
back to, not its own separate settings - a real, natural follow-up if
ever wanted, not built here.

Not yet live-verified against a real call reaching a customized
greeting or a group mailbox - same category of gap as the rest of this
module's voicemail/routing features.

## Hardware desk phones

The browser softphone covers a single operator well, but a team wants a
real phone at each desk. The architectural question that mattered:
does that need new SignalWire-side infrastructure, or can it reuse
what's already here?

**Live-verified 2026-09-15, against the user's real trial account**
(before any code was written): created a real SIP Endpoint (the exact
`POST /api/relay/rest/endpoints/sip` call `action_provision_signalwire_sip`
already makes), confirmed it advertises standard telephony codecs
(PCMU/PCMA/G722, not just WebRTC-only ones), then sent a raw SIP
REGISTER over UDP directly to the guessed `{space}.sip.signalwire.com:5060`
and got back a genuine `401 Unauthorized` / `WWW-Authenticate: Digest` /
`Server: SignalWire Proxy` challenge - confirming standard SIP-over-UDP
is genuinely supported (not just WebSocket/WebRTC), no new
SignalWire-side work needed for a physical desk phone to share the
same kind of SIP Endpoint credentials as the softphone. (A follow-up
hand-rolled digest-auth REGISTER against that same guessed domain got
a second 401 - at the time assumed to be a bug in the toy test
client's own MD5 math; per "The SIP domain gotcha" above, the real
cause was almost certainly the guessed domain itself being wrong, not
the digest math, though this specific early test was never re-run
against the real domain to confirm.)

**Design, per the user's own confirmed choices**: each desk phone gets
its **own** SIP Endpoint (`signalwire.desk_phone`), not a second
registration on the user's existing softphone endpoint - sidesteps a
real, documented gap (RFC 5626/`sip.instance`) in how well modern
SIP/WebRTC stacks handle multiple simultaneous registrations on one
shared endpoint. An inbound call rings the softphone and every one of
the user's desk phones **at once** (`_sip_targets()` builds one `<Sip>`
per device inside the same `<Dial>` already used for the softphone and
ring-group fallback step - both now go through this one helper).

**Auto-provisioning is real, not "paste these values into the phone
by hand"**: `GET /signalwire/provisioning/<filename>` matches either
brand's own real expected request pattern (`<mac>.cfg` for Yealink,
`cfg<mac>.xml` for Grandstream) and serves that phone's SIP credentials
already filled in. Point the phone's own "Auto Provision Server URL"
at it directly, or - for a whole office at once - point a DHCP scope's
option 66 at this same URL; the phone appends its own filename
automatically either way, so adding a phone to the network is genuinely
zero-touch once its MAC is registered in Odoo.

**A MAC address isn't secret** - this endpoint is deliberately public
(`auth='public'`, a physical phone can't hold an Odoo session), so
anyone who guesses or observes a valid MAC can fetch that one phone's
live SIP password. This is the same trust model every hosted-PBX
provider's own auto-provisioning uses - the blast radius is one
already-revocable device credential, not the account - but it's worth
stating plainly rather than glossing over. An unknown or
not-yet-provisioned MAC gets a plain 404, logged at `warning` so
unexpected requests are visible.

**Not live-tested against real hardware** - no physical Yealink or
Grandstream phone was available to point at this. Everything above
was verified at the protocol level (the real SIP challenge) and the
config-file content was checked against each brand's own documented
key/P-value names, not against an actual device's boot log. The
user's own first real phone is the real test here.

## Transferring calls between users

The Transfer button on an active call now offers a colleague search
(backed by `res.users.search_signalwire_colleagues`, scoped to the
caller's own company) instead of requiring a raw SIP username to be
typed by hand, alongside two actions:

- **Transfer** (blind) - the existing, already-working mechanism: a
  plain SIP REFER, immediate, no confirmation the target actually
  answers.
- **Check First** (attended/"warm") - holds the current call, places
  a separate, ordinary outbound call to the chosen colleague so the
  agent can confirm they're actually free, then **Complete Transfer**
  (shown on the active-call view for as long as that consultation call
  is in progress) bridges the original caller directly to the
  colleague via SIP.js's own REFER-with-Replaces support, or **Cancel**
  returns to the original caller if the colleague can't take it.

**A real architectural constraint attended transfer runs into**:
`voip_oca`'s own `VoipAgent` is built around exactly one call at a
time - `onInvite` auto-rejects a second *incoming* call with 486 while
one is active, and `call()`/`hold()`/every lifecycle handler reference
a single `this.session` field throughout. That guard is about
receiving a second call, not placing one, so it doesn't block this -
but it meant patching in a genuinely second, independent
`consultationSession` slot (`voip_agent_attended_transfer.esm.js`)
rather than just adding a new method, plus session-parameterized
audio-routing logic (`_setCallAudioForSession`) so the agent hears the
colleague, not the held original caller, during consultation.

**Not yet live-tested end to end** (two real provisioned softphones,
one placing an attended transfer to the other) as of writing - the
REFER-with-Replaces call shape was confirmed correct by reading
SIP.js's own vendored source directly (`Session.refer()` accepts
another `Session` as its target for exactly this, and requires that
target to already be `Established`), but whether SignalWire's own
proxy correctly completes the 3-way signaling and actually bridges the
two remote parties once REFER succeeds - freeing both of the agent's
own local legs - is genuinely unconfirmed. This module's own JS has no
automated test coverage at all (established gap, same as every other
frontend piece here), so this one specifically needs a real live test
before being considered done, not just a clean code read.

## The live receptionist panel

A new **Receptionist Panel** menu (visible only to the SignalWire
Receptionist security group) shows two things in real time: every
active inbound call, and the whole team's status.

**A real inbound call** (`signalwire.live_call`, distinct from
`voip_oca`'s own `voip.call` - that's a per-user call *log* entry,
this is the call's own routing-journey record, tracked by SignalWire's
own `CallSid` from the moment the inbound webhook fires until it ends)
can be routed straight from the panel:

- **Send** (blind) - redirects the live call to a chosen colleague's
  SIP targets via SignalWire's Compatibility API "Update a call"
  endpoint. The caller never hangs up and calls back; the call's own
  live cXML flow just changes.
- **Check First** - parks the caller on a "please hold" loop (the same
  redirect mechanism, pointed at a small new hold-loop route) while
  the receptionist places a perfectly normal, separate outbound call
  via their own already-working softphone to confirm the colleague can
  take it. **Deliberately not a 3-way conference bridge** - no new
  SIP/media complexity, no second session on the caller's own leg at
  all, matching the same "server-side call control, not browser-side
  session juggling" principle Phase C's attended transfer needed
  vendored-code surgery to achieve for a *different* problem (two
  parties the *agent themselves* is bridging). Once ready, **Send**
  completes the actual transfer the normal way.
- **Voicemail** - redirects into the exact same `<Say>`+`<Record>`
  flow the personal fallback chain already uses.

**Team status** combines two genuinely different signals rather than
inventing a new presence system: Odoo core's own `im_status` (browser
online/away/offline, driven by `mail.presence`/`bus` - confirmed by
reading Odoo 19's own source rather than assuming) says whether
someone's logged into Odoo at all, and this module's own new
`signalwire_call_state` (idle/ringing/on a call, reported live by each
user's own softphone - patched onto `VoipAgent`'s lifecycle handlers)
says whether they're actually on the phone, since SignalWire itself
has no presence API at all (confirmed earlier in this project). A
**Message** button per person reuses core's own `useOpenChat` hook -
the exact same one `AvatarCardPopover`'s "Send message" button already
uses - to open a real Discuss chat, no new backend needed for that
part at all.

**A real, pre-existing bug caught while building this**: none of this
module's own "self-service" `res.users` fields (forwarding number,
personal ring group, voicemail toggles) had ever actually been added
to `SELF_WRITEABLE_FIELDS`/`SELF_READABLE_FIELDS` - only `voip_oca`'s
own fields were, in its own `res_users.py`. A plain (non-admin) user
editing their own Preferences got a real `AccessError`, confirmed live
via `with_user()` against an actual non-admin user, contradicting this
module's own long-standing documentation that these were self-service.
Fixed alongside adding `signalwire_call_state` to the same list.

**Not live-tested** - the bus broadcast targets the Receptionist
security group directly (`bus.bus._sendone()` requires an actual
record, not a plain string; every connected user is already auto-
subscribed to their own group records via
`ir_websocket._build_bus_channel_list()`, confirmed by reading Odoo
19's own source, so this needed no extra client-side subscription
code) - the mechanism is sound by inspection but hasn't been exercised
against a real inbound call and a real second browser tab yet.

## Testing

`signalwire.server._get_sip_domain`/`action_setup_click2call`,
`res.partner.format_partner`'s E164 formatting (requires `phonenumbers`
installed to actually exercise, not just fall back silently - see
above),
`res.users` provisioning/release, `search_signalwire_colleagues`
(excludes self and non-provisioned users, scoped by company),
`set_signalwire_call_state`, `get_signalwire_receptionist_roster`
(group-gated), self-write access to this module's own "self-service"
fields (the real pre-existing gap above, tested against an actual
non-admin user via `with_user()`, not just admin/superuser context),
and the fallback-chain methods (profile-phone shortcut, partner
matching), `signalwire.phone_number` inbound-routing configuration
(including Call Group, IVR Menu, and business-hours routing, with a
real `resource.calendar` record in the test setup for the inside/
outside-hours cases), `signalwire.call.group`, `signalwire.ivr.menu`/
`.option` (including a second real `res.company` record to prove
`check_company` actually rejects a cross-company target, not just that
the field exists), `signalwire.live_call` (redirect URLs, state
transitions, the provisioned-softphone guard), and the inbound,
fallback-chain, group-fallback, IVR entry/digit-handling,
route-to-user/route-to-voicemail/hold-loop, and voicemail-complete/
voicemail-transcription webhook controllers (real HTTP round trips via
`HttpCase`, including the voicemail recording fetch mocked at the
`requests` layer) are all covered, along with `signalwire.voicemail`'s
own mark-read/unread, systray-data, and record-rule (a plain user
can't see or touch someone else's) behavior - nothing beyond Phase 1's
own already-tested API client makes a real HTTP call in this suite.
The systray/player and receptionist panel JS itself isn't unit tested
- this repo has no JS test harness set up (same gap as every other
module's own frontend code here).

`signalwire.desk_phone` (MAC normalization/validation, provision/
release against a mocked client), the provisioning controller (both
brands' filename patterns, unknown/unprovisioned MAC -> 404), and the
multi-device ring behavior (a user's softphone + desk phone(s) both
appear in the first `<Dial>`, a teammate with only a desk phone still
gets reached by the ring-group step) are covered the same way - 73
tests total in this module, all against a mocked SignalWire client;
nothing here has been exercised against real hardware.
