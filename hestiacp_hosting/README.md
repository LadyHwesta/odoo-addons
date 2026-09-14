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
   HestiaCP package name, and resource-limit fields (disk, bandwidth,
   domains, mailboxes, databases, backups) - the latter are
   **informational only**, see **HestiaCP API notes** below for why.
3. **Checkout**: plain `website_sale`. Confirming an order (which, on a
   real storefront, only happens after payment succeeds) creates:
   - a `contract.contract` with one recurring `contract.line` matching
     the package's price, billed monthly - `contract`'s own cron takes
     it from there for every renewal after the first.
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
   and enter the *exact* name of the package you created in step 2.
   The resource-limit fields are for your own reference - keep them
   matching what's actually on the HestiaCP package by hand.
5. **Payments → Providers → Stripe** (this module depends on
   `payment_stripe`, so it's already installed) - enable it, add your
   Stripe API keys, and make sure tokenization ("Allow saving payment
   methods" / `allow_tokenization`) is turned on so `website_sale`
   actually offers customers the option to save a card - without that,
   no `payment.token` ever gets created and renewals fall back to
   manual payment for everyone.
6. Publish the product on the website (`website_sale` as normal) and
   take a test order through checkout, saving the card when prompted.

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
