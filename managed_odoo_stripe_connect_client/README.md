# Managed Odoo Stripe Connect - Client

The other half of `managed_odoo_stripe_connect` (which lives in
Meskis' own Odoo) - this one gets deployed onto a managed Odoo
instance customer's own separate database, as part of their
`managed_odoo_instances` app bundle.

## Zero standalone value, by design

Every call this module makes goes to Meskis' own bridge, using a
bearer token scoped to this instance's own Stripe Connect account.
It never sees, stores, or needs Meskis' own Stripe Platform secret -
and structurally can't usefully hold one anyway, since
`application_fee_amount` only works when the *platform's* own
credentials are exercised at charge time (see the other module's own
README for the full reasoning). The bridge side
(`managed_odoo_stripe_connect`, which holds the Platform secret) stays in
Meskis' own unpublished repo. This half lives in the public `odoo-addons`
repo because it's installed on customers' own servers, which only download
public repos, and it goes with its LGPL-3 licence and source (Meskis Works'
customer agreement, Part A 7.2). It does nothing without Meskis' bridge on
the other end.

## Setup

Settings > General Settings > Stripe Connect (System group only) -
three fields, filled in once from whatever Meskis hands you during
onboarding: Bridge URL (Meskis' own Odoo address), Bridge Token (your
own scoped credential), Stripe Account ID (your own `acct_...`, for
reference).

## `StripeConnectBridgeClient`

Same shape as every other API client in this project
(`SignalWireClient`, `UpCloudClient`, `HestiaCPClient`) - one class, a
couple of methods, errors normalized into `StripeConnectBridgeError`.

- `create_onboarding_link()` - a fresh Stripe-hosted URL; redirect the
  user there directly, the actual Standard-account signup/KYC happens
  entirely on Stripe's own pages.
- `create_payment_intent(amount_minor_units, currency, reference)` -
  charges through Meskis' own Platform, with Meskis' cut applied
  automatically. Amount is in the currency's own minor units (cents
  for USD), matching Stripe's own convention.

`res.company._get_stripe_connect_bridge_client()` returns a ready
instance built from the three Settings fields above, raising a clear
`UserError` if they're not filled in yet.

## Deliberately a foundation, not a drop-in `payment_stripe` replacement

Core Odoo's own `payment_stripe` checkout flow makes several different
Stripe API calls across one purchase (customer creation, setup
intents, the inline card-entry UI, then finally the actual charge) -
transparently proxying *all* of that through the bridge would need a
much larger, fully generic relay, and wasn't built here. What exists
now covers the one call that actually matters for monetization - the
real charge, with the fee correctly applied - callable from anywhere
in the customer's own Odoo (a custom sale-order confirmation step, an
invoice "Pay via Stripe Connect" button, etc.).

**Not yet wired into an actual self-service checkout page.** Building
one (collecting a card via Stripe.js/Elements, then calling
`create_payment_intent`) is real follow-on work - flagged here plainly
rather than implied to already exist.

## Testing

7 tests, `requests` mocked at the boundary - onboarding-link and
charge calls, error propagation (both Stripe-side error bodies and
network failures), URL-joining edge cases, and the company-level
client-getter's own configured/unconfigured behavior.

**Not live-tested** - same prerequisite as the other module: nothing
here can be exercised for real until Meskis' own Stripe account has
Connect Platform capability enabled and at least one customer has
completed real Standard-account onboarding.
