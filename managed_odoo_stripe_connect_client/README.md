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

## Checkout through Meskis

The customer keeps core `payment_stripe`'s own checkout: website orders,
invoice payments, saved cards, manual capture, refunds and Apple/Google Pay.
On their Stripe provider (Accounting/Website > Payment Providers > Stripe),
**Take payments through Meskis** asks the bridge for the platform's
publishable key, their Stripe account id and a forwarding secret, and fills
the provider in. It then holds no Stripe secret key of its own.

- Every Stripe call core makes goes to the bridge (`_send_api_request`
  override), which makes it with the platform key on this account only and
  adds Meskis' fee to every charge.
- Stripe.js loads with `stripeAccount` set (payment_stripe's own
  `StripeOptions` hook), so cards are taken on the customer's own account.
- Stripe's payment updates reach the usual `/payment/stripe/webhook`,
  passed on by the bridge and signed with the forwarding secret, so core's
  own signature check accepts them.
- Test mode isn't offered: the bridge's key decides live or test. A
  provider in test mode is left disabled when switched over, to be enabled
  on purpose.
- **Stop taking payments through Meskis** switches back and disables the
  provider.

Not covered: Stripe terminals in the Point of Sale (`pos_stripe`), which use
a provider secret key directly.

## Testing

22 tests, `requests` mocked at the boundary - onboarding-link and
charge calls, error propagation (both Stripe-side error bodies and
network failures), URL-joining edge cases, and the company-level
client-getter's own configured/unconfigured behavior.

**Not live-tested** - same prerequisite as the other module: nothing
here can be exercised for real until Meskis' own Stripe account has
Connect Platform capability enabled and at least one customer has
completed real Standard-account onboarding.
