# SignalWire SMS

Phase 3 of the SignalWire VoIP project (see
[`signalwire_voip`](../signalwire_voip/) for Phase 1 and
[`signalwire_voip_click2call`](../signalwire_voip_click2call/) for
Phase 2). Two related but separate capabilities, both built on the
same `signalwire.subproject`/`signalwire.phone_number` core:

## Team messaging

Send an SMS to any contact from their own partner form (the **Send
SMS** button, next to Meetings/Opportunities-style stat buttons) - a
small compose wizard picks which of your own SignalWire numbers to
send from (defaults to one that isn't dedicated to a resold customer)
and sends it via `signalwire.phone_number.send_sms()`.

Every message - sent or received - gets logged to the matched
contact's own chatter, no new inbox to check. Matching is **best-
effort**: it compares the last 10 digits of the other party's number
against a contact's `phone`/`mobile` field, normalized to digits-only
on both sides (SQL's own `like` can't do this - `"5556102107"` isn't a
substring of the literal stored string `"+1 (555) 610-2107"` even
though the digits match, since punctuation breaks up the run - see
`signalwire.sms._log_to_partner_chatter`'s own docstring). No match
just means the message isn't logged anywhere but the `signalwire.sms`
audit table itself (Sales -> VoIP -> Messages).

## Reselling SMS

A subproject's customer gets **two independent ways** to actually use
their number, matching how the user wanted this to work whether or not
they're on hosted Odoo:

1. **Their own SignalWire API credentials.** *Not* the subproject's
   own `auth_token` - that comes back masked from SignalWire's API by
   design (see `signalwire_voip`'s own README). Instead,
   `signalwire.subproject.action_issue_customer_token` creates a
   separate, permission-scoped **Project API Token** tied to that
   subproject (`messaging` + `numbers` only) - confirmed live
   2026-09-15 that this DOES return the real secret, once, and that it
   authenticates as **`{subproject account_sid}:{token}`** (the
   subproject's own SID as the username, not the parent project's -
   easy to get backwards). A technical customer plugs this into any
   Twilio-compatible library directly; Odoo never sees what they send.
2. **A simple portal page** (`/my/sms`) for a customer who'd rather
   use a UI: their number(s), recent messages, a send box, their
   access token(s) (issue/revoke), and a webhook URL field they can
   set themselves.
3. **Webhook forwarding.** If a customer sets `sms_webhook_url` on
   their number (via the portal, or a staff member on the backend
   form), every inbound message also gets POSTed there as JSON
   (`{from, to, body, sid, received_at}`) - lets them wire this into
   whatever system they already run, independent of both options
   above. Best-effort/fire-and-forget - a failure is logged
   (`signalwire.sms.webhook_status`) rather than raised, so a
   customer's own endpoint being down doesn't affect Odoo's own
   receipt of the message.

## The inbound webhook

`POST /signalwire/sms/inbound` - one URL for every number (looked up
by the message's `To` field), same convention as the click-to-call
phase's own inbound webhook. Creates a `signalwire.sms` record, best-
effort logs it to a matched contact's chatter, and forwards it to the
owning number's webhook if one is configured. Responds with an empty
cXML `<Response></Response>` - "received, no auto-reply."

## Important: revoking a customer's token is NOT confirmed to work

**Confirmed live 2026-09-15, twice, deliberately**: deleting a
customer access token (`DELETE /api/project/tokens/{id}`) genuinely
removes its own metadata record - a second `DELETE` or a `GET` on the
same token ID afterward both correctly `404`, so it's really gone from
SignalWire's own token list. **But the secret itself kept
authenticating successfully against the Compatibility API at least 15
seconds after "deletion," with no sign of it ever actually stopping.**

This is the same broken-DELETE pattern already documented in
`signalwire_voip`'s own README for `signalwire.subproject.action_close`
- possibly a trial-account restriction on destructive actions
specifically (returning success without completing, rather than
revealing the restriction with an error), not confirmed either way
since production-account behavior hasn't been tested.

**Practical consequence**: `action_revoke`/the portal's "Revoke"
button are still built and shipped (they at least clean up the token
list, and may work correctly on a production/verified account), but
neither this module nor its UI copy should be trusted as an actual
security boundary yet. If a customer's SMS access genuinely needs to
be cut off, escalate to SignalWire support directly rather than
relying on Revoke alone - this is flagged in the portal page's own
copy and in `action_revoke`'s docstring.

## Important: SMS capability isn't automatic (10DLC / Campaign Registry)

**Confirmed live 2026-09-15**: every number available to purchase in
the user's trial account - across every US area code and toll-free -
came back with `SMS: false` capability. This is not a bug or a code
gap: as of December 2025, newly purchased US numbers have **no SMS
capability at all** until the business completes SignalWire's
Campaign Registry (10DLC) brand + campaign registration - a real-
world compliance/anti-spam requirement at the carrier level, outside
this module's (or SignalWire's own API's) control. This blocks BOTH
use cases above equally until done:

- **Team messaging** needs at least one SMS-enabled number for the
  business's own outbound/inbound use.
- **Reselling** likely needs the *reseller's own* Brand registered
  with the resold numbers attached to a Campaign - exactly how this
  works for subproject-owned numbers specifically hasn't been
  researched yet; that's the real next step before promising SMS
  resale to an actual paying customer, not a code change.

Everything in this module is built and tested against the correct,
documented request/response shapes regardless - once a number is
actually SMS-enabled, no code changes should be needed.

## Testing

Business logic (chatter matching + its digit-normalization fix,
webhook forwarding success/failure, token issue/revoke, the compose
wizard's default-number logic) is covered by mocked tests. The inbound
webhook and the full portal flow (including the deliberately-still-on
CSRF protection, and that a portal user can only see/act on their own
subproject's numbers, tokens, and messages - never another customer's)
are covered by real `HttpCase` HTTP round trips against the local test
server. Nothing in the automated suite makes a real HTTP call to
SignalWire.

**Not live-verified**: an actual SMS send/receive round trip - blocked
by the 10DLC gate above, not by anything in this module. `send_sms`
and the inbound webhook use the same, well-documented Twilio-
compatible `Messages` resource shape already confirmed working
elsewhere in this project (namecheap-style domains aside, this is the
same Compatibility API surface `signalwire_voip` already exercises
successfully for calls/numbers) - live-verify this the moment a real
SMS-capable number exists.
