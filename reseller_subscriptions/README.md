# Reseller Subscriptions

Meskis Works - the user's own live Odoo instance - sells three
independent recurring services out of it: web hosting
([`hestiacp_hosting`](../hestiacp_hosting/)), domain registration/
renewal ([`namecheap_domains_sale`](../namecheap_domains_sale/)), and
VoIP/SMS/video ([`signalwire_voip_sale`](../signalwire_voip_sale/),
[`signalwire_sms`](../signalwire_sms/),
[`telehealth_booking_signalwire`](../telehealth_booking_signalwire/)).
Each already bills recurringly through the vendored OCA `contract`
engine, but before this module a customer using more than one had no
single place to see what they'd got, and SignalWire's own billing had
a real gap. This module is Phase 1 of a larger plan (see
`/Users/tiesam/.claude/plans/indexed-imagining-gosling.md` at the time
this was built) - treating "a whole managed Odoo instance" as a
billable product is scoped as a deliberately separate, later phase,
not attempted here.

## What was actually there before this module

Confirmed by reading the real code, not assumed:

- `hestiacp.account` and `namecheap.domain` had each independently
  grown the exact same shape: `contract_id` (Many2one
  `contract.contract`) + `payment_token_id` (Many2one `payment.token`)
  + `_charge_invoice()` + `_cron_auto_charge_due_invoices()` -
  `namecheap.domain`'s version is a near line-for-line copy of
  `hestiacp.account`'s.
- **SignalWire never got this treatment.**
  `signalwire_voip_sale`'s own `_signalwire_provision_number_lines`
  created a real `contract.contract` per purchased number at checkout,
  but never stored a back-reference to it anywhere - neither
  `signalwire.phone_number` nor `signalwire.subproject` had a
  `contract_id`/`payment_token_id` field, and there was no auto-charge
  cron. In practice: a SignalWire customer's invoices were never
  auto-charged, and nothing suspended a non-paying one.
- **`signalwire.phone_number.action_release()` wasn't billing-aware** -
  releasing a number at SignalWire left its contract line running, so
  a customer who cancelled a number kept being billed for it. Its own
  docstring already claimed release "stops its monthly charge" - it
  didn't, until this module.
- Hosting's change-package wizard
  (`hestiacp_hosting/wizards/hestiacp_account_change_package.py`)
  already worked but was staff-only - no portal route called it.
- Domains had no upgrade/downgrade (no tier concept) and **no cancel
  action at all**.
- No unified view existed: `/my/hosting` (hosting only, read-only) and
  `/my/sms` (SignalWire texting/tokens, not billing) were the only
  dedicated portal pages; domains and the VoIP contract itself had
  none. The vendored `contract` module's own generic `/my/contracts`
  lists every contract lumped together with no self-service actions.

## Design: additive only, nothing already-live gets touched

This is a **live production system, real customers, real money**.
Everything this module adds to `hestiacp_hosting`'s and
`namecheap_domains_sale`'s own models is purely additive (new fields,
new methods, via `_inherit`) - neither module's existing, already-
working billing code is refactored or risked. The one exception is
`signalwire_voip_sale`, which explicitly is **not yet trusted in
production** per its own README ("Not live-verified" throughout) - a
small, additive, non-behavior-changing patch was made there (see
below), since closing the SignalWire billing gap genuinely required
somewhere for the checkout flow to hand off the new data, and doing
that as a hook call is safe whether or not this module is installed.

### `contract.billing.mixin`

A new `AbstractModel` (`models/contract_billing_mixin.py`) extracting
`_charge_invoice()`/`_cron_auto_charge_due_invoices()` from the
near-identical logic already proven in `hestiacp.account`/
`namecheap.domain`. Used by the new SignalWire billing below.
**Deliberately not retrofitted onto `hestiacp.account`/
`namecheap.domain` themselves** in this pass - their own versions
already work; nothing about them needs to change for this mixin to
close SignalWire's gap. A consuming model needs `contract_id`
(Many2one `contract.contract`), `payment_token_id` (Many2one
`payment.token`), and `partner_id` already defined with those exact
names - the mixin declares none of them itself, to avoid any risk of
redefining a field an inheriting model already has.

### Closing the SignalWire billing gap - the hook pattern, and why

`signalwire.phone_number` gains `contract_id`/`payment_token_id`
(inheriting the mixin), a `_subscription_summary()`, and an
`action_release()` override that ends the number's contract line.

The tricky part: `signalwire_voip_sale`'s own
`_signalwire_provision_number_lines` (in `sale_order.py`) is where the
contract actually gets created, and it's the natural place to capture
the checkout's payment token too - but that module doesn't (and
shouldn't) depend on `reseller_subscriptions`. Writing
`contract_id`/`payment_token_id` directly from that method would crash
with "unknown field" on any install that doesn't have this module -
i.e. it would have broken `signalwire_voip_sale` standalone. **Fixed
with a no-op hook**, the same pattern `telehealth_booking`'s own
`_get_premium_video_url()` already uses for its SignalWire upsell: a
small new file, `signalwire_voip_sale/models/signalwire_phone_number.py`,
adds `_signalwire_after_provisioned(contract, checkout_transaction)` -
a no-op by default - called right after the contract is created.
`reseller_subscriptions` overrides it to actually store the
back-reference. Safe either way; `signalwire_voip_sale` itself never
has to know this module exists. (Bumped `signalwire_voip_sale` to
`19.0.1.2.0` for this.)

### The "stop renewing" action for domains - not as simple as ending the line

`namecheap.domain.action_cancel_renewal()` is new (there was no cancel
action at all before). It does two things, and **both are load-bearing**:

1. Ends the domain's currently-open `contract.line` (`date_end` set to
   today) - stops future invoices being generated.
2. Moves `state` to a new `'cancelled'` value (added via
   `selection_add`, additive to the existing Selection).

(2) matters because `namecheap_domains_sale`'s own `_cron_renew_domains`
gates the real, actual-money Namecheap-side renewal purely on "no
unpaid invoice exists on the contract" - **not** on whether the
contract line is still open. Ending the contract line alone would have
meant: no more customer invoices ever get created, so the "no unpaid
invoice" check trivially always passes, so the cron would have kept
renewing the domain for real at Namecheap indefinitely, with nothing
billing the customer for it. Moving `state` off `'active'` is what
actually stops that (the cron's own search domain is
`[('state', '=', 'active'), ...]`) - confirmed by reading its code, not
assumed. This needed no change to `namecheap_domains_sale` itself: the
new state value alone is enough, since that module's existing cron
already filters on `state`.

### A missing ACL, found by actually trying to read the data as a portal user

`hestiacp.account` and `signalwire.phone_number` already had a
portal-read access row (`base.group_portal`, read-only) granted by
their own modules (`hestiacp_hosting`, `signalwire_sms`) - inherited
here for free since this module depends on both. **`namecheap.domain`
had none at all**: nobody had ever needed one, since domains never had
a self-service surface before this module. Without it, every
ownership-scoped `search()` this controller does against
`namecheap.domain` would have come back empty for every portal user,
silently breaking that entire product line's self-service (not just
non-owners - everyone). Added one new read-only ACL row for it, same
shape as the other two.

### `_subscription_summary()` - an adapter, not a deep mixin

Each of the three consumer models gets one new method returning a
uniform dict (`name`, `state`, `next_invoice_date`, `monthly_amount`,
`can_upgrade`, `can_cancel`, `has_payment_method`, `portal_view_url`).
This is what lets one portal template render all three genuinely
different models generically, without forcing them into one real
inheritance hierarchy - a smaller, safer surface than a full mixin
retrofit would have been.

## The unified portal

- `GET /my/subscriptions` - every subscription across all three lines
  in one table, each row's actions driven by its summary dict.
- `GET/POST /my/subscriptions/hosting/<id>/upgrade` - a portal-safe
  wrapper around the *existing* `hestiacp.account.change.package`
  wizard (ownership check, then calls the same `action_confirm()` -
  no upgrade logic duplicated).
- `POST /my/subscriptions/hosting/<id>/cancel`,
  `.../domain/<id>/cancel_renewal`, `.../signalwire/<id>/release` -
  one route each, ownership-checked, calling the model's own method.
  Each kind has its own explicit route (not a generic
  `<action>`-from-the-URL dispatcher) so the action a request can take
  is always fixed by which route actually matched, never chosen
  dynamically from user input.
- `POST /my/subscriptions/<kind>/<id>/payment_method` - assigns one of
  the customer's own already-saved cards (Odoo core's own
  `/my/payment_method` page is where a card actually gets tokenized -
  not rebuilt here) to a subscription. `kind` is looked up against a
  small hardcoded dict of the three known kinds, never used to
  construct a model name dynamically.
- Ownership is enforced the same way every other portal controller in
  this repo already does it (see `signalwire_sms`'s own
  `controllers/portal.py`): search scoped to the logged-in user's own
  `partner_id`, then `.filtered()` against the id in the URL - a
  record that isn't actually theirs just silently no-ops rather than
  raising, same convention.
- One new `portal_my_home` tile, "My Subscriptions" - the existing
  Hosting and SMS tiles stay as-is, they serve a different purpose
  (control-panel access, the texting UI) than pure billing.

## What's NOT done here, on purpose

- **`hestiacp.account.action_terminate()` has the exact same class of
  bug `action_release()` had** - it deletes the HestiaCP user and
  marks the account terminated, but never touches the contract, so a
  terminated hosting account's billing doesn't actually stop either.
  Found while reading the code for this module, but `hestiacp_hosting`
  is explicitly hands-off in this pass (see "Design" above) - **this
  needs a decision and a follow-up fix**, it's called out here rather
  than silently left undocumented.
- Full automated multi-tenant Odoo provisioning (treating "we run your
  nonprofit/club/paramedic-suite Odoo for you" as a billable, instantly
  self-serviceable product) is a distinct, much larger infrastructure
  project - scoped for a later phase, not attempted here.
- SignalWire's own subproject-close and customer-token-revoke gaps
  (documented in `signalwire_voip`'s/`signalwire_sms`'s own READMEs -
  both silently no-op despite reporting success) are unrelated to
  billing and untouched here.

## Testing

Model-level: the new SignalWire billing methods
(`_signalwire_after_provisioned`, `action_release` ending the contract
line, the auto-charge cron), `namecheap.domain.action_cancel_renewal`
(including a test that directly proves a cancelled domain drops out of
`_cron_renew_domains`'s own search domain, without needing to run that
cron for real), and `_subscription_summary()`'s shape on all three
models. Controller-level (`HttpCase`, real HTTP round trips): the list
page shows only the logged-in user's own subscriptions, and every
action route has an explicit "another user can't act on this" test
alongside its "the owner can" counterpart. All mocked at the same
external-API boundary the underlying modules' own tests already mock
at (`HestiaCPServer._get_client`, `SignalWireServer._get_client`,
`PaymentTransaction._send_payment_request`) - nothing here makes a
real HTTP call to HestiaCP, SignalWire, or a payment gateway.

Not live-verified against the real Meskis Works production instance -
built and tested entirely against the local `testing/` harness, same
as every other module in this repo. The user runs the actual
production rollout themselves once satisfied.
