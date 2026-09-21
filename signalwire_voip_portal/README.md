# SignalWire Portal Support Calling

Extends [`signalwire_voip_click2call`](../signalwire_voip_click2call/)'s
internal call routing out to the customer *portal* - an external
contact can request a support callback, or (a step further, not yet
built - see below) place a real live browser call to reach an agent
directly, as an alternative to opening a ticket or using Discuss.

## The two hard requirements this was built around

1. **Never an external call.** A portal visitor must never be able to
   reach an arbitrary phone number through the business's own
   SignalWire account - only a single, fixed internal destination.
2. **Gated per contact**, with room for tiers - not every portal
   customer gets this at all, and "live call" is meant to be a step
   above "callback request," not a separate unrelated switch.

## `res.partner.signalwire_portal_support_tier`

A Selection field (`none`/`callback`/`live_call`) - `live_call`
always includes `callback` too (checked as `tier != 'none'` for the
callback path, `tier == 'live_call'` for the live-call path once that
exists). Two independent enforcement layers, not just a hidden portal
button:

- Every portal-facing controller route checks the tier server-side
  directly (`/my/support/call`'s own `support_call_form()` 404s a
  contact with `tier == 'none'` even hitting the URL directly) - the
  same "never trust that hiding a button is enough" discipline the
  receptionist panel's own backend methods already use.
- A dedicated **SignalWire Portal Calling** security group, kept in
  sync with the tier field automatically (`res.partner.
  _sync_signalwire_portal_group()`, triggered from both `res.partner`
  and `res.users`' own `create()`/`write()` - a partner's tier is very
  often set *before* their actual portal login exists, so the sync has
  to work regardless of which record gets created first) - this is
  what the new models' own `ir.model.access`/`ir.rule` actually gate
  on, matching Odoo core's own idiom for gating a portal *capability*
  (confirmed by reading `project`'s own portal access rules) rather
  than checking a `res.partner` field directly from an `ir.rule`
  domain, which can't reference the calling user's own partner that
  way.

## Callback requests (built)

`signalwire.callback_request`: a portal contact submits a phone
number (pre-filled from their own profile, editable) and an optional
note at `/my/support/call`. Deliberately a separate model from
`signalwire.live_call` (`signalwire_voip_click2call`) - that one
represents a real, already-in-progress call keyed by a live
SignalWire `call_sid`; a callback request has no call in progress
yet, and conflating the two would mean an awkward nullable `call_sid`
and two different lifecycles jammed into one model.

On creation: broadcasts to the same `group_signalwire_receptionist`
group `signalwire_voip_click2call`'s own receptionist panel already
listens on (`bus.bus._sendone()`, no new channel plumbing at all) and
posts to the request's own chatter. The receptionist panel itself
gains a new **Callback Requests** section (patched in via
`callback_requests.esm.js`/`.xml`, not a separate page) - **Claim**
(assigns it to whoever clicked, schedules a "call back" activity for
them - there's no natural single owner until someone claims it, so no
activity exists before that point), **Call Now** (literally
`agent.call({number: req.phone_number})` - the exact same already-
working outbound-call path every other click-to-call in this project
uses, zero new SIP/VoIP code), and **Done**.

## Live browser-to-agent calling (not yet built)

A deliberately separate, later phase. The real design constraint,
resolved during planning: the portal browser must never be able to
dial anything itself - not just as a UI/business rule, but
structurally, so "no external calls" holds even if the client-side JS
were ever tampered with. The plan (not yet implemented): the portal
widget only ever *registers* a short-lived SIP identity and waits;
the *server* places the real call via the Compatibility API (the
exact same `SignalWireClient.compat_post()` already used throughout
this project) targeting that identity, and once the portal browser
auto-accepts, the webhook's own cXML response `<Dial>`s the fixed
internal "Portal Support" call group - reusing `_route_dial_cxml()`/
`_sip_targets()` from `signalwire_voip_click2call` verbatim, the same
helpers already proven working since that module's own Phase 1.

This has real, genuinely new mechanics that haven't been tried in
this project yet (a server-initiated call bridging into a browser
SIP.js session that auto-accepts, rather than SignalWire's own
inbound-PSTN gateway originating it) - build and live-test it as its
own clearly separate step, not assumed to work by analogy to what
already works.

## Testing

`res.partner`'s own tier-to-group sync (including the creation-order
gap - a portal login created after the tier was already set, and vice
versa), `signalwire.callback_request`'s claim/complete lifecycle
(including the "already claimed" guard and the activity being
scheduled/closed correctly), and the portal controller's own real
gate (`HttpCase`, an actual authenticated portal session, confirming
both the page and the submit route 404 or silently create nothing for
a `tier == 'none'` contact - not just a mocked check) are all covered.
No live SignalWire calls happen in sub-phase 1 at all - "Call Now" in
the receptionist panel is the exact same already-tested `agent.call()`
path, nothing new to verify there beyond what `signalwire_voip_
click2call`'s own test suite already covers.
