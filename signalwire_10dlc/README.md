# SignalWire 10DLC Registration

Built the same day a real SMS send attempt from the user's own DID
(`+17078021991`) was rejected outright:
`421717 - "From must belong to an active campaign."` Every resold
SignalWire customer hits this exact same wall on their own numbers,
not just Meskis Works' own - US carriers require a registered "brand"
(business identity) and "campaign" (messaging use case) with The
Campaign Registry before any number can send A2P SMS.

## What's confirmed live vs. sourced from docs

**Live-verified 2026-09-15** against the user's real SignalWire
account (not just documentation):

- `POST/GET /api/relay/rest/registry/beta/brands` - real, working;
  returned the user's own real "Meskis Works" brand.
- `POST/GET /api/relay/rest/registry/beta/brands/{brand_id}/campaigns`
  - real, working; returned the real campaign nested under that brand.
- `GET /api/relay/rest/registry/beta/campaigns/{campaign_id}/numbers`
  and `.../orders` - **the one thing SignalWire's own docs don't
  document at all** (no exact path given anywhere for number
  assignment) - confirmed by reading real data back: an "order" is
  how a specific phone number (by its own SID) gets tied to a
  campaign, addressed directly by `campaign_id` with **no brand
  prefix needed**.
- **No subaccount/subproject scoping exists anywhere on this API** - a
  query-string `account_sid` was silently ignored. Brands and
  campaigns live in one flat list at the reseller's own top-level
  account; the actual link to a specific resold customer happens at
  the *order* step, which references that customer's own number by
  SID regardless of which subproject it lives in.

**Sourced from SignalWire's own docs, not independently confirmed for
every value**: `legal_entity_type`'s four values, `company_vertical`'s
23 values, `sms_use_case`'s 25 values. Only `PRIVATE_PROFIT`/
`TECHNOLOGY`/`CUSTOMER_CARE` respectively have been seen in real live
data (the user's own brand/campaign). If SignalWire ever rejects one
of the other values, that's the real API disagreeing with its own
documented enum.

**Not live-tested**: an actual brand/campaign submission through this
code. That requires real customer business data (EIN, legal address)
and incurs a real, non-refundable registration fee plus a recurring
campaign fee with a 3-month minimum - not something to do
speculatively. The first real submission through this module should
be an actual resold customer's, or a deliberate test the user
explicitly asks for and knowingly pays for.

## Design

- **Extends `SignalWireClient`** (`signalwire_voip/models/signalwire_api.py`)
  with a fifth API surface, `registry_get`/`registry_post` - the same
  one-client-many-surfaces pattern already used for the Compatibility/
  Relay/Project/Video APIs, not a new client class.
- **`signalwire.brand`** - one per resold customer's real business
  identity (never the reseller's own). `state` is mirrored directly
  from whatever string SignalWire's own API reports, not a hardcoded
  transition graph - the real state machine beyond "pending" hasn't
  been independently confirmed, and guessing at it would be worse
  than reflecting the API's own value.
- **`signalwire.campaign`** - one messaging use case per brand,
  inherits `reseller_subscriptions`'s own `contract.billing.mixin`
  directly for the monthly fee - the exact reason that abstraction was
  worth building generically in Phase 1. `min_commitment_end_date`
  (submission + 3 months) blocks `action_cancel()` before then,
  matching the real "3-month minimum, charged upfront" billing term.
- **`signalwire.phone_number`** (a *third* `_inherit` on this model -
  `reseller_subscriptions` already added `contract_id`/
  `payment_token_id`) gains `campaign_id` and
  `action_request_sms_enablement()` - the actual, deliberate opt-in
  trigger. A number with no campaign simply can't send SMS yet;
  nothing here does this automatically at checkout.
- **Self-service portal**, extending `signalwire_sms`'s own `/my/sms`
  (a new view inheriting its template, not touching its controller) -
  a customer sees an "Enable SMS" action per number, which either
  creates the number-assignment order directly (if they already have
  a campaign) or routes them to a new `/my/sms/compliance` form first.
  The customer fills in and submits their own business details -
  they're the one certifying the info, so they're the one who should
  enter it, not the reseller on their behalf.

## A real, non-obvious robustness gotcha worth knowing

The three status-poll crons (`_cron_check_brand_status`,
`_cron_check_campaign_status`,
`_cron_check_campaign_assignment_status`) each wrap their per-record
work in `self.env.cr.savepoint()`, not a bare `try/except`. A failed
write mid-loop (e.g. SignalWire reporting a state string this
project's own `Selection` field hasn't enumerated) poisons the whole
surrounding Postgres transaction, not just that one iteration - every
later record's write in the same cron run would then fail too, silently,
with a confusing "current transaction is aborted" error. The savepoint
rolls back only the one record that failed, letting the rest of the
batch keep processing normally.

## Testing

Local `testing/` harness, same as every other module in this repo -
`SignalWireClient.registry_get`/`registry_post` (tested in
`signalwire_voip`'s own suite), all three models' actions and status-
poll crons (including that one erroring record doesn't stop the rest
of a cron run), the 3-month cancellation guard, and portal ownership
scoping (one customer can't see or act on another's brand/EIN/number) -
all with `requests` mocked at the `SignalWireServer._get_client`
boundary, same convention as every other SignalWire client in this
repo.
