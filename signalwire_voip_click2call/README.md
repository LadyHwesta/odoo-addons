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

1. Have a `signalwire.server` already configured (see `signalwire_voip`).
2. On that server's form, click **Setup Click-to-Call** - creates the
   one `voip.pbx` record every user's softphone shares (idempotent,
   safe to click again if the server's Space ever changes).
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

## Live-verified 2026-09-15, against the user's real trial account

- **The SIP-over-WebSocket hostname is NOT the bare Space domain.**
  `wss://{space}.signalwire.com` (the plain Space domain) serves the
  web dashboard and refuses/redirects any WebSocket upgrade attempt to
  the login page. The real endpoint lives at a distinct host with
  `.sip.` inserted: `wss://{space-name}.sip.signalwire.com` - confirmed
  via a raw WebSocket handshake (curl 8.21's native `wss://` support),
  which came back `101 Switching Protocols` / `Server: SignalWire
  Proxy` with the `sip` subprotocol accepted. `_get_sip_domain()`
  builds this correctly.
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

## Testing

`signalwire.server._get_sip_domain`/`action_setup_click2call`,
`res.users` provisioning/release and the fallback-chain methods
(profile-phone shortcut, partner matching), `signalwire.phone_number`
inbound-routing configuration, and the inbound, fallback-chain,
voicemail-complete, and voicemail-transcription webhook controllers
(real HTTP round trips via `HttpCase`, including the voicemail
recording fetch mocked at the `requests` layer) are all covered, along
with `signalwire.voicemail`'s own mark-read/unread, systray-data, and
record-rule (a plain user can't see or touch someone else's) behavior
- nothing beyond Phase 1's own already-tested API client makes a real
HTTP call in this suite. The systray/player JS itself isn't unit
tested - this repo has no JS test harness set up (same gap as every
other module's own frontend code here).
