# Namecheap Domain Reselling

Connects Odoo to Namecheap's reseller API so this business can check
domain availability and price domains at Namecheap's real cost plus a
percentage markup. **This is Phase 1 (backend core) of a three-phase
build - see "Not yet built" below before assuming customers can
actually buy a domain through this module today.**

## Why a percentage markup instead of flat pricing

TLD costs vary enormously - a `.com` costs a few dollars a year at
wholesale, while some ccTLDs run well over $100 - so a single flat
markup amount would make cheap TLDs overpriced and expensive TLDs
underpriced. A percentage scales with Namecheap's own cost instead,
applied globally (one setting, not configured per TLD - see
`namecheap.server.markup_percentage`) per the choice made when this
was scoped.

## Architecture (Phase 1)

1. **`namecheap.server`** - the reseller account's credentials
   (API User/Key/Username, the whitelisted client IP, sandbox vs.
   production) plus the business's `markup_percentage`. One record in
   practice, kept together the same way `hestiacp.server` in the
   sibling `hestiacp_hosting` module holds one hosting server's
   connection settings and policy together.
2. **`models/namecheap_api.py`** - the HTTP client. Namecheap's API is
   XML over POST (not REST/JSON) - see its own docstring for the full
   wire format and the two gotchas that aren't obvious from a first
   read of the docs (per-account IP whitelisting, and production API
   access itself being gated behind 20+ domains / $50+ balance / $50+
   spent in 2 years - the sandbox has none of that).
3. **`namecheap.tld.price`** - a local cache of Namecheap's own
   per-TLD registration/renewal cost, refreshed by a daily cron
   (`namecheap.tld.price._cron_sync_pricing`) from
   `namecheap.users.getPricing`. Namecheap's own docs describe that
   sheet as large and slow-changing and recommend fetching it once and
   caching it - this table *is* that cache; nothing in this module
   queries pricing live per customer search. `sell_register_price`/
   `sell_renew_price` are computed from the cached cost plus the
   server's markup percentage.
4. **`namecheap.server.check_domain_availability()`** - checks a list
   of domains via `namecheap.domains.check` and returns each one's
   availability plus a marked-up sell price - from the cached TLD
   sheet for a normal domain, or from Namecheap's own ad-hoc
   `PremiumRegistrationPrice` (marked up the same way) for a premium
   domain, since those don't follow the per-TLD sheet rate at all.
5. **`namecheap.domain`** - one record per domain this business owns.
   Created by hand for now (Phase 3 hasn't wired up automatic creation
   from an actual purchase yet - see below), but already the anchor
   point for [`namecheap_hestiacp`](../namecheap_hestiacp/), a small
   separate bridge module that can deploy an owned domain onto a
   HestiaCP hosting account without either module depending on the
   other - install it only if this business actually uses HestiaCP.
   Has its own **Nameservers** field + "Update Nameservers" button
   (calling `namecheap.server.set_custom_nameservers()`) for pointing a
   domain's DNS anywhere it needs to go - Namecheap's own default DNS
   if left blank, a hosting provider's nameservers, Cloudflare's
   (assigned per-zone once added there, for its proxy/CDN/DDoS
   features), or anywhere else. This is deliberately independent of
   HestiaCP - a domain doesn't need `hestiacp_account_id` set at all to
   use it, and `namecheap_hestiacp`'s own DNS toggle (see its README)
   builds on top of this rather than replacing it.

## Live-verified against the sandbox (2026-09-14)

Namecheap's own documentation pages return HTTP 403 to automated
fetching, so unlike `hestiacp_hosting`'s HestiaCP client (checked
against HestiaCP's own GitHub source before ever touching a real
server), this was originally built from a real third-party open-source
client's request/response code plus community-documented examples -
and then actually tested against a real Namecheap sandbox account,
the same way HestiaCP's own assumptions got corrected once tested
live. Connection, balance check, and `check_domain_availability()` all
worked exactly as built. The pricing sync (`users.getPricing`) had two
real bugs, both fixed: `ProductType` must be `'domain'` (lowercase,
singular - the response itself comes back `Name="domains"`, which
doesn't matter since only the request value is checked), and the
`ProductCategory` request parameter **doesn't filter anything
server-side** - every category (register, renew, transfer, redemption,
reactivate, landrush, preorder) comes back in one response regardless
of what's requested, so the sync makes one call and filters
client-side rather than two calls each wrongly assumed pre-filtered.
Verified with a real sync of 1088 TLDs and sane real-world prices
(`.com` $13.98 register / $18.08 renew, matching Namecheap's own public
pricing closely).

**Still not live-tested**: `set_custom_nameservers()` (used by
`namecheap_hestiacp`'s deploy action) - its request format was
confirmed by reading a real client's source rather than assumed
outright, but calling it for real needs an actual registered domain in
the sandbox account, which Phase 3 (registration) doesn't create yet.
Worth a live pass once that exists.

## Setup

1. Create a **sandbox** Namecheap account at sandbox.namecheap.com
   (this is a completely separate signup from a real Namecheap
   account) and enable API access there - the sandbox has no eligibility
   gate, unlike production.
2. **Domains → Namecheap Accounts** → create a record with that
   sandbox account's API User/Key/Username, this Odoo server's own
   outbound IP (must also be added to the sandbox account's API
   whitelist), leave **Sandbox** checked, and set a markup percentage.
3. **Test Connection** - should report the sandbox account's (fake)
   balance.
4. Run the pricing sync manually the first time rather than waiting
   for the daily cron (Settings → Technical → Scheduled Actions →
   "Namecheap: Sync TLD Pricing" → Run Manually), then check
   **Domains → TLD Pricing** for cached costs and computed sell prices.
5. Only once the whole flow (through whichever phase is built) has
   been tested against the sandbox should a *second*, real
   `namecheap.server` record be created with production credentials
   and Sandbox unchecked.

## Known simplifications / not yet built

- **No domain search or checkout UI.** `check_domain_availability()`
  is a model method, not yet exposed anywhere a customer can reach -
  Phase 2 (a website search box, likely integrated with
  `website_sale`) isn't built.
- **No actual registration.** Buying a domain still requires calling
  `namecheap.domains.create` with the customer's registrant contact
  info (decided at scoping time: pulled from the customer's existing
  billing address, not a separate WHOIS-contact step) - Phase 3, not
  built. Nothing in this module registers a real domain yet.
  `namecheap.domain` records are created by hand in the meantime.
- **No renewal billing.** A real domain needs a recurring
  `contract.contract` (reusing the `contract` module already vendored
  for hosting) *and* an actual call to `namecheap.domains.renew` at
  renewal time - invoicing alone doesn't renew a domain at the
  registrar. Not built.
- **No low-balance alert yet**, even though
  `namecheap.server._get_available_balance()` exists to support one.
  This matters more than it might sound: registering a domain draws
  down the real Namecheap balance immediately, with no separate
  authorize/capture step - if a customer has already paid via Stripe
  but the balance is too low at that moment, the business has been
  paid and can't deliver. Should be built before Phase 3 goes live
  with real money.
- **USD only.** The pricing cache assumes one currency; multi-currency
  storefronts aren't in scope.
- **Domain transfers not built.** `namecheap.domains.transfer.create`
  exists and is possible for a specific allowlist of TLDs, but wasn't
  scoped for this build - a real follow-up if the business wants to
  accept transfers-in later.

## Testing

All business logic is covered by tests that mock
`namecheap.server._get_client()` - nothing in the automated suite makes
a real HTTP call, including to the sandbox (that verification is a
separate, manual step - see the gap noted above). Run via this repo's
`testing/` harness:

```
cd testing && ./pg_start.sh
python3 ~/dev/odoo-19/odoo-bin --addons-path=... -d namecheap_test \
  -i namecheap_domains --test-enable --test-tags=/namecheap_domains \
  --stop-after-init --log-level=test
```
