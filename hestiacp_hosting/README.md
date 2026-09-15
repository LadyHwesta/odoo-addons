# HestiaCP Hosting Billing

Sells hosting packages through `website_sale`, bills them recurringly via
OCA's `contract` module, and provisions/suspends/terminates the
customer's account on a HestiaCP server automatically as payment comes
in, lapses, or the plan is cancelled.

## Why build this instead of using Paymenter or FOSSBilling

Both already solve this exact problem, including a HestiaCP integration
(Paymenter's is maintained by the HestiaCP team itself). Chosen to build
in Odoo anyway so this hosting business's billing lives in the same
system as the rest of the consulting/invoicing work, not because either
tool is lacking.

## Architecture

1. **`hestiacp.server`** - one record per HestiaCP server (hostname, API
   Access Key/Secret). A `server_id` field on both this and
   `product.template` from day one, even with a single server, so
   adding a second one later isn't a refactor.
2. **`product.template`** extended with `is_hosting_package`, a
   HestiaCP package name, a billing period (monthly/quarterly/yearly -
   `contract`'s own `recurring_rule_type`, which already supports all
   three), and resource-limit fields (disk, bandwidth, domains,
   mailboxes, databases, backups) - the latter are **informational
   only**, see **HestiaCP API notes** below for why. To offer more than
   one cadence for the same plan (e.g. a cheaper annual option),
   create a separate product per period, same package/server on each -
   there's no single-product cadence picker on the storefront.
3. **Checkout**: plain `website_sale`. Confirming an order (which, on a
   real storefront, only happens after payment succeeds) creates:
   - a `contract.contract` with one recurring `contract.line` matching
     the package's price and billing period - `contract`'s own cron
     takes it from there for every renewal after the first.
   - a `hestiacp.account` record, immediately provisioned: creates the
     HestiaCP user with the package assigned, generates a random
     password and emails it (never stored in Odoo past that one
     message - see **Known simplifications** below).
4. **`hestiacp.account`** - the lifecycle tracker (`draft` → `active` →
   `suspended` → `terminated`), independent of any one order (a renewal
   invoice doesn't touch this record). A daily cron
   (`_cron_check_payment_status`) first attempts to auto-charge any due
   invoice against the customer's saved payment token (see next point),
   then suspends an active account once its contract has an invoice
   still unpaid past 7 days, unsuspends it once caught up, and
   terminates it (deletes the HestiaCP user) after 30 days *actually
   spent suspended* - not immediately, and not merely 30 days
   invoice-overdue (an account can be very overdue before ever being
   noticed - e.g. after a cron outage - and still gets the full grace
   period suspended first; see the `suspended_date` field).
5. **Automatic renewal charging** - if the customer tokenized their
   card at checkout (`website_sale`'s own "save this card" option), the
   resulting `payment.token` is captured onto `hestiacp.account` from
   the order's `get_portal_last_transaction()`. The same cron above
   then charges that token against any due invoice using Odoo's own
   server-initiated token-charge API (`payment.transaction.
   _charge_with_token()` - the same mechanism a "pay with saved card"
   button uses, just invoked from a cron instead of a click). One
   attempt per invoice, not a retry loop; a customer with no saved
   token (declined to save one, or paid by a non-tokenizing method)
   just falls back to the pre-existing manual-payment/suspend flow,
   same as before this existed.
6. **Hosting Service Agreement gate** - a hosting order can't reach
   `/shop/payment` until the customer explicitly accepts the current
   `hestiacp.agreement` (Sales → Configuration → Hosting Agreement),
   covering acceptable use plus an anti-spam/mandatory-unsubscribe
   clause. Enforced server-side via website_sale's own
   `_get_shop_payment_errors` extension point (the same mechanism core
   uses to block payment when there's no shipping method available),
   not a client-side-only checkbox, so it can't be skipped by disabling
   JS - see **Customer agreement** below for the full flow and why it's
   built this way instead of Odoo's native T&C checkbox or e-signature
   fields.
7. **Package upgrade/downgrade** - a "Change Package" button on an
   active `hestiacp.account` (staff-only, not yet self-service) opens a
   wizard to move it to a different package on the same server. See
   **Changing an account's package** below.
8. **Migrating an existing, already-paid customer** - Sales →
   Configuration → Hosting → Migrate Existing Customer provisions a
   real HestiaCP account today without billing for time already paid
   to a previous host. See **Migrating an existing customer** below.

## Changing an account's package

`hestiacp.account`'s "Change Package" button (only shown while the
account is `active`) opens a wizard offering any other hosting product
on the *same* HestiaCP server - moving an account to a different server
isn't supported here, only reassigning it to a different package on the
one it's already on.

**Downgrade safety is enforced by HestiaCP itself, not this module.**
`v-change-user-package` is called without its optional `FORCE`
argument (verified against the command's own source, 2026-09-14):
without it, HestiaCP compares the account's actual current usage - web/
DNS/mail domains, databases, cron jobs, disk, bandwidth - against the
new package's limits and refuses the whole change if any of them don't
fit, with a specific "Package doesn't cover ... usage" error. That
error surfaces as a normal Odoo error dialog (it's a
`HestiaCPAPIError`, itself a `UserError`) telling staff exactly what
the customer needs to remove first (an extra domain, mailboxes, etc.)
before the downgrade can go through - this module doesn't reimplement
that check itself.

**Billing takes effect at the next renewal, not prorated.** The
HestiaCP-side package change (and its resource limits) applies
immediately on success. The recurring price, however, only changes
starting the account's next invoice:

- If nothing has been invoiced on the account yet (a same-day change
  right after provisioning), the existing `contract.line` is just
  repointed at the new product - there's no already-paid period to
  preserve, so the very next invoice is already at the new price.
- Otherwise, the current line is ended at its next renewal date and a
  new line for the new product starts there, leaving the
  already-invoiced period untouched.

Either way there's a small, deliberate mismatch for whatever's left of
the currently-paid period: the account has the new package's resources
but is billed at the old price for the rest of it, in both directions
(upgrade or downgrade). Real proration (crediting/charging the
difference for the partial period) isn't built - this trades a bit of
revenue precision for not having to get partial-period math right.

## Migrating an existing customer

For onboarding a customer moving from another host (Planet Hoster,
etc.) who's already paid through some future date - **Sales →
Configuration → Hosting → Migrate Existing Customer**. This exists
because the normal path (a `sale.order` confirming) always creates a
recurring line that's due for its first invoice immediately, which
would bill the customer again for time they've already paid for
elsewhere.

The wizard asks for the customer, the hosting package, an optional
username (to preserve one they're already used to, if it's free on
this server - otherwise the normal auto-generated one), and the date
their already-paid-for period with their old host actually ends. On
confirm, it:

1. **Provisions the real HestiaCP account immediately** - the exact
   same `v-add-user` call a normal checkout makes.
2. **Creates the recurring contract**, but with the line's
   `recurring_next_date` set explicitly to the given renewal date
   instead of today. This works because that field, despite being
   "computed," is declared `readonly=False` and only auto-computed as
   a *default* - an explicit value passed at creation sticks, the same
   way a normal renewal's own advance of that field does later. The
   invoicing cron leaves the line alone until that date arrives, then
   bills normally from then on.

No invoice is created and no charge is attempted at migration time -
only real provisioning happens immediately; billing genuinely waits.

**Domains being migrated alongside hosting need no special handling** -
`namecheap_domains`/`namecheap_hestiacp` (see that repo's own modules)
have no billing/contract coupling at all yet (domain registration
billing is a later phase, not built), so creating a `namecheap.domain`
record and using its existing "Deploy to HestiaCP" button is already
exactly as billing-free as this wizard, with no changes needed there.

## Customer agreement (Hosting Service Agreement)

`website_sale` ships a native "I agree to the terms & conditions"
checkout checkbox (`accept_terms_and_conditions`), and `sale.order` has
native e-signature fields (`signature`/`signed_by`/`signed_on`). Neither
was usable here:

- The native checkbox is a pure client-side UI gate - it has **no
  persisted field**, so there's no record of what a given customer
  actually accepted or when.
- The native signature flow is **deliberately disabled for every
  website order** - `website_sale`'s own `_compute_require_signature`
  override forces `require_signature = False` whenever `website_id` is
  set, specifically so the ecommerce checkout isn't blocked on it.

So this module builds its own, small mechanism instead:

- **`hestiacp.agreement`** holds the agreement text (`body_html`) and a
  `version` string - edit it under Sales → Configuration → Hosting
  Agreement. Only one should be `active` at a time; archive rather than
  edit in place once real customers have accepted it, so a past
  acceptance still points at the text that was actually agreed to. The
  seed record in `data/hestiacp_agreement_data.xml` is a **draft
  template, not legal advice** - see the warning on the record's own
  form view and the comment at the top of that file; it needs review by
  a real lawyer for your jurisdiction (especially Section 7,
  Liability, left as a placeholder) before relying on it.
- Visiting `/shop/payment` with an unaccepted hosting order in the cart
  adds an error via `_get_shop_payment_errors` linking to
  `/hosting/agreement`, which shows the current agreement's text and a
  required checkbox posting to `/hosting/agreement/accept`. Accepting
  stamps `sale.order.hestiacp_aup_agreement_id` /
  `hestiacp_aup_accepted_on` / `hestiacp_aup_accepted_ip` and redirects
  back to `/shop/payment`, which is now unblocked.
- On order confirmation those three fields are copied onto the new
  `hestiacp.account` as a permanent record, independent of the order.
  A backend-confirmed order that never went through the checkout (e.g.
  a salesperson confirming a phone quote) has no acceptance to copy -
  `action_provision` notes that on the account's chatter rather than
  blocking provisioning, since the business may have gotten agreement
  some other way.

## HestiaCP API notes (verified live 2026-09-14)

A full `v-add-user` → `v-suspend-user` → `v-unsuspend-user` →
`v-list-user` → `v-delete-user` cycle was run against a real server
while building this, cross-checked against HestiaCP's actual
`web/api/index.php` and `func/main.sh` source (not just its docs page).
A few things came out different from the original assumption, all
already fixed in the code here:

- **`v-add-user`'s real argument order is `USER PASSWORD EMAIL
  [PACKAGE] [NAME] [LASTNAME]`** - package is arg4, not name. The
  package is assigned in this same call; no separate
  `v-change-user-package` call is needed on first provisioning.
- **Don't send `returncode=yes`.** It makes HestiaCP discard the real
  command output and return only the bare exit code - harmless for
  action commands (which return nothing anyway) but silently breaks
  any `v-list-*` command's actual data.
- **Check the always-present `Hestia-Exit-Code` response header**, not
  the HTTP status code or response body alone - HestiaCP maps its exit
  codes to a range of HTTP statuses (401 for an auth/permission
  failure, 422 for a bad argument, etc.), so status-only handling isn't
  uniform, but the header always carries the real exit code (0 =
  success). On failure the body is a human-readable `Error: ...`
  message; on success it's empty (action commands) or the real data
  (`v-list-*` with a `json` format argument).
- **HestiaCP's Access Key permission system has exactly 6 built-in
  categories** (`billing`, `mail-accounts`, `phpmyadmin-sso`,
  `purge-nginx-cache`, `sync-dns-cluster`, `update-dns-records` - see
  `install/common/api/*` in the HestiaCP source), not arbitrary
  per-command grants. Only **`billing`** covers what this module needs
  for the account lifecycle (`v-add-user`, `v-delete-user`,
  `v-suspend-user`, `v-unsuspend-user`, `v-change-user-package`,
  `v-change-user-password`) - grant the key that one category.
  **No category at all covers `v-add-user-package`,
  `v-change-user-package-value`, or `v-list-user-packages`** - package
  *definitions* genuinely cannot be managed through the Access Key API,
  confirmed by enabling every available category and still getting
  "doesn't have permission" for those three. Packages have to be
  created/edited by hand in HestiaCP (Server → Packages); this module
  only ever assigns an *existing* package name to a new account.

## Setup

1. On HestiaCP: **Server → Access Keys** → create a key, grant it the
   **billing** permission category, and add the Odoo server's IP to
   the key's IP access list (if you haven't set `IP=''`/unrestricted).
2. Create the actual hosting package(s) by hand under **Server →
   Packages** first - the API can't do this part (see above).
3. In Odoo: **Sales → Configuration → HestiaCP Servers** → add the
   server (hostname like `https://host.example.com:8083`, the Access
   Key and Secret), then **Test Connection**.
4. Create a hosting product, tick **Hosting Package**, pick the server,
   enter the *exact* name of the package you created in step 2, and
   pick a **Billing Period**. The resource-limit fields are for your
   own reference - keep them matching what's actually on the HestiaCP
   package by hand. Want quarterly and annual options for the same
   plan? Duplicate the product, change only the price and billing
   period, and point it at the same server/package name.
5. **Payments → Providers → Stripe** (this module depends on
   `payment_stripe`, so it's already installed) - enable it, add your
   Stripe API keys, and make sure tokenization ("Allow saving payment
   methods" / `allow_tokenization`) is turned on so `website_sale`
   actually offers customers the option to save a card - without that,
   no `payment.token` ever gets created and renewals fall back to
   manual payment for everyone.
6. Publish the product on the website (`website_sale` as normal) and
   take a test order through checkout, saving the card when prompted.
7. Review and adapt the seeded Hosting Service Agreement (**Sales →
   Configuration → Hosting Agreement**) before going live - it's a
   draft template, not legal advice; see **Customer agreement** above.

## Known simplifications / not yet built

- **No customer-chosen password at checkout.** The original scoping
  considered letting the customer set their own HestiaCP password
  during checkout; this build generates one and emails it instead - a
  standard, simpler pattern (and it's what most hosts already do for a
  first login). A password-reset self-service flow through the portal
  would be a good follow-up if a mailed password isn't desired
  long-term.
- **Portal page done** (`/my/hosting`, with a "Hosting" entry on `/my`)
  - shows the customer's own package, username, status, and an "Open
    control panel" link (to HestiaCP's own login page - see the module
    description for why there's no true SSO). Portal users only ever
    see their own accounts (`ir.rule` in `security/hestiacp_security.xml`).
- **Automatic renewal charging done** - see Architecture point 5 above.
  Not yet built: any customer-facing retry/dunning flow beyond the
  existing suspend-after-7-days behavior (a failed charge just means
  the account eventually suspends on schedule, same as an unpaid
  invoice always did), and no portal "add/update payment method"
  self-service flow (currently only settable at initial checkout).
- **No package management via the API** - see HestiaCP API notes
  above. Packages are a one-time-per-plan manual step in HestiaCP
  itself, not something this module can automate given how HestiaCP's
  Access Key permissions are actually scoped.
- **Package upgrade/downgrade done, staff-only** - see **Changing an
  account's package** above. Not yet built: a portal self-service
  version (a customer picking their own new plan rather than asking
  staff to run the wizard), and real proration - both would be good
  follow-ups if this business ends up wanting either.
- **Existing-customer migration done** - see **Migrating an existing
  customer** above. One-at-a-time only; if migrating a large batch of
  customers turns out to be tedious through the wizard, a CSV-import
  version would be a reasonable follow-up.

## Testing

All business logic (provisioning, suspend/unsuspend/terminate, the
payment-status cron, the sale-order-confirmation hook) is covered by
tests that mock `hestiacp.server._get_client()` - nothing in the
automated test suite makes a real HTTP call (the live verification
above was done by hand, separately, against a real server). Run the
automated suite via this repo's `testing/` harness:

```
cd testing && ./pg_start.sh
python3 ~/dev/odoo-19/odoo-bin --addons-path=... -d hestiacp_test \
  -i hestiacp_hosting --test-enable --test-tags=/hestiacp_hosting \
  --stop-after-init --log-level=test
```
