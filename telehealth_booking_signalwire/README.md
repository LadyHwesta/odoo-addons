# Telehealth Booking - SignalWire Premium Video

Fills in [`telehealth_booking`](../telehealth_booking/)'s own
`_get_premium_video_url` hook with a real SignalWire Video backend -
the upgrade path for a provider whose bookings have outgrown Discuss's
peer-to-peer video calling (see that module's own README for exactly
why that ceiling exists).

## Setup

1. Have a `signalwire.server` already configured (see `signalwire_voip`).
2. On a provider's own user form (Telehealth tab), click **Upgrade to
   Premium Video** - flips their tier. Nothing else happens yet: no
   SignalWire subproject or billing contract gets created until their
   *first* booking actually requests a video link, keeping "upgrading"
   itself a free, instant, reversible action.

## What happens on a premium booking

1. `calendar.event._get_premium_video_url` provisions a real
   SignalWire Video room (`POST /api/video/rooms`, confirmed live
   2026-09-15) the first time a link is requested for that specific
   booking, and - on that same first call - provisions the provider's
   own `signalwire.subproject` and a metered, post-paid billing
   contract (`res.users._ensure_telehealth_video_billing`) if they
   don't already have one.
2. `videocall_location` is set to an **Odoo-hosted** URL
   (`/telehealth/signalwire/join/<token>`) - not a raw SignalWire link
   with a token baked in. This matters: a SignalWire room token is a
   JWT, and a booking made today for an appointment next week would
   otherwise carry an expired credential by the time anyone actually
   clicks it. The join controller generates a **fresh** room token on
   every visit instead - exactly the same pattern Discuss's own
   `calendar/join_videocall/<token>` route already uses for its own
   link.
3. The join page itself loads a vendored copy of SignalWire's own
   browser SDK (`@signalwire/js` 3.30.0, MIT-licensed, the real
   `dist/index.umd.js` build - its `package.json` lists this exact
   file under `"unpkg"`, confirmed by fetching and inspecting it) and
   calls `new SignalWire.Video.RoomSession({token, rootElement}).join()`,
   the standard integration pattern per SignalWire's own docs.
   Vendored rather than pulled from a CDN at request time, same
   convention as `voip_oca`'s own vendored `sip.js`.

## Billing: reuses signalwire_voip_sale's own CDR mechanism

Rather than build a separate metered-billing pathway for video,
`signalwire_voip_sale`'s `contract.line` gained a
`signalwire_usage_type` field (`telecom`/`video`) so the exact same
`is_signalwire_metered` + real-per-record-CDR + itemized-PDF-statement
mechanism already built (and already fed back per explicit user
feedback to be per-record, not a lump sum) now applies to video too -
see that module's own README for the full design. This module adds
the video-specific half: `signalwire.subproject._sync_video_cdrs`.

**Video's own usage API is a genuinely different, two-level shape**
than Calls/Messages - list this subproject's room sessions for the
period, then list *each session's own members* for the actual per-
participant duration/cost. Confirmed live 2026-09-15:
`/api/video/rooms`, `/api/video/room_tokens`, and
`/api/video/room_sessions` all exist and respond correctly. **Not**
independently verified: the exact member-level field names
(`id`/`name`/`join_time`/`duration`/`cost_in_dollars`) and the
`room_sessions` date-filter param names (`started_at>`/`started_at<`,
guessed from the Video API's own snake_case field-naming convention,
not confirmed against a real filtered response) - no real room
session exists yet to check either against, since generating one
needs an actual joined WebRTC call, the one thing that structurally
can't be driven from a script. Confirm the moment a real premium
telehealth call has actually happened.

## What this does NOT do

- **No auto-downgrade for non-payment.** Same accepted gap as
  `signalwire_voip_sale`'s own number-rental billing.
- **No room cleanup.** A booking's SignalWire room is never deleted -
  harmless (rooms cost nothing until someone actually joins), but
  worth knowing before assuming old bookings clean up after
  themselves.
- **No recording wired up yet**, even though it's one of the concrete
  reasons Premium is worth having (see `telehealth_booking`'s own
  README) - `record_on_start` exists on the Rooms API and isn't set
  here. A reasonable next addition once the base flow is proven live.

## Testing

Tier-based routing (premium gets a telehealth join URL, basic still
gets Discuss, no server configured falls back to Discuss), room
provisioning + billing setup, the two-level video-CDR sync (mocked),
and the join controller itself (a real `HttpCase` HTTP round trip,
including that a fresh token is generated on every visit) are all
covered. Nothing in the automated suite makes a real HTTP call to
SignalWire, and nothing drives an actual browser to join a call - see
the confidence-level notes above for what that leaves genuinely
unverified.
