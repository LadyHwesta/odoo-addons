# Namecheap Domain Storefront

Phase 2+3 of the domain-reselling build (see [`namecheap_domains`](../namecheap_domains/)'s
own README for Phase 1 - the connection, cached TLD pricing, and manual
nameserver management). This module is what actually **sells** a domain:
a public search page, real registration at checkout, and yearly recurring
renewal billing that keeps registering it year over year rather than just
invoicing for it.

## Setup

1. Create exactly one `product.template` with **Domain Registration**
   checked (Sales → Products → the "Domain Registration" page on the
   product form) and a Namecheap Account selected. The search page and
   checkout always use the *first* such product found - there's normally
   only ever one, since price is per-domain, not per-product.
2. Set the product's `type` to **Service** (or any non-stockable type) -
   nothing here is shippable.
3. Customers reach the search page at **`/domains`** (linked from the
   website's main menu as "Register a Domain").

## How a purchase actually works

1. **Search** (`/domains/search`, `namecheap.server.check_domain_availability`)
   checks a domain live against Namecheap and returns its sell price
   (cached TLD price + markup, or a premium name's own ad-hoc price -
   see `namecheap_domains`'s README for how that's computed).
2. **Add to cart** (`/domains/add_to_cart`) re-checks availability and
   price itself rather than trusting anything the page already showed -
   a result can go stale between being shown and being added (someone
   else registers it in between) - then adds a line via the normal
   `_cart_add()` website_sale pathway.

   Two things make a domain line different from a normal product line:
   - **`_cart_find_product_line` is overridden** (same technique
     `website_event_sale` uses for event tickets) so two different
     domains added through the same generic product never merge into
     one line with quantity 2 - each domain is its own distinct thing
     being bought, not "more of the same."
   - **`price_unit` is written directly** after the line is created.
     This works because `sale.order.line.price_unit` is a *computed*
     field with `readonly=False` (same "computed default, editable
     afterward" pattern this project already relies on for
     `contract.line.recurring_next_date` in `hestiacp_hosting`'s
     migration wizard) - nothing re-triggers that compute on an
     existing line afterward, so the write sticks.
3. **Checkout** happens through website_sale's normal cart/payment flow -
   nothing custom here. Once payment succeeds and the order confirms:
4. **`sale.order._action_confirm()`** is overridden to register every
   domain line for real, mirroring `hestiacp_hosting`'s own
   `_hestiacp_provision_hosting_lines` pattern almost exactly:
   - Calls `namecheap.domains.create` (via `namecheap.server.register_domain`)
     with the ordering partner's own billing address used as all four
     required contact roles (Registrant/Tech/Admin/AuxBilling) - see
     `res.partner._namecheap_registrant_fields()`. There's no separate
     "WHOIS contact info" step at checkout.
   - Creates a `contract.contract` (vendored OCA `contract` +
     `contract_sale`) with one yearly `contract.line`, so renewal gets
     invoiced automatically going forward.
   - Creates the `namecheap.domain` record itself, linked back to the
     order and the new contract, and captures the checkout transaction's
     saved card (`payment_token_id`) if the customer tokenized one - the
     same mechanism `hestiacp.account` uses for hosting renewals.

## Renewal billing - and actually renewing, not just invoicing

Three crons (`data/ir_cron.xml`), all on `namecheap.domain`/`namecheap.server`:

- **`_cron_auto_charge_due_invoices`** (daily): for every domain with a
  saved payment token, charges any posted-but-unpaid invoice on its
  contract via Odoo's server-initiated token-charge API - identical
  mechanism to `hestiacp.account._charge_invoice`. No saved token means
  no auto-charge; the invoice just waits for manual payment.
- **`_cron_renew_domains`** (daily): runs the charge attempt above
  first, then for every domain within `RENEW_LEAD_DAYS` (15) of
  `expires_on` with **no unpaid invoice** on its contract, calls the
  real `namecheap.domains.renew` and advances `expires_on` by a year.
  **Deliberately does not renew with an unpaid invoice** - unlike
  hosting, there's no suspend-then-terminate grace period to sit in
  first; a domain either gets renewed before it expires or it lapses
  (subject to Namecheap's own post-expiration redemption grace period,
  outside this module's control either way).
- **`_cron_check_balance`** (daily, on `namecheap.server`): posts an
  internal chatter note when the account's available balance drops
  below `low_balance_threshold` (default $100). Registering or renewing
  a domain draws the real balance down immediately with no separate
  authorize/capture step - if it runs dry between a customer paying and
  this module actually calling Namecheap, the business has been paid
  and can't deliver.

## What this does NOT do

- **No multi-year checkout pricing UI yet.** `namecheap_years` defaults
  to 1 and the search page's add-to-cart button only ever adds a single
  year; the model support for longer initial terms exists
  (`sale.order.line.namecheap_years`, `register_domain`'s own `years`
  param) but nothing in the storefront UI exposes it yet.
- **No transfer-in flow.** Only new registrations
  (`namecheap.domains.create`) - moving an existing domain from another
  registrar isn't part of this module.
- **A registration race is possible, after payment.** If the exact
  domain gets registered by someone else between add-to-cart and
  checkout completing (rare, since domains aren't reserved on
  add-to-cart), `register_domain` raises during order confirmation -
  *after* the customer's already been charged. Not specially handled,
  the same class of risk `hestiacp_hosting` accepts for a username
  collision - flagged here explicitly since real money and a whole
  domain are at stake.
- **Not live-verified against the sandbox yet.** Everything here is
  built against Namecheap's documented request/response shape (and, for
  the gaps their docs don't cover, a real open-source client's source -
  see `namecheap_domains`'s own README for what's already been
  live-verified there). `domains.create` and `domains.renew`
  specifically have **not** been exercised against a real sandbox
  domain yet - do that (register one real free sandbox domain end to
  end through the actual storefront) before trusting this against a
  production account.

## Testing

Business logic (cart line separation, price_unit override, order
confirmation → registration + contract creation, the renewal and
balance crons) is covered by tests mocking `namecheap.server._get_client()`
- nothing here makes a real HTTP call to Namecheap. The website
controller and JS search page are not covered by automated tests yet
(no HTTP-level test in this suite) - smoke-test the `/domains` page by
hand after installing.
