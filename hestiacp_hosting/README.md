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
   domains, mailboxes, databases, backups). "Sync Package to Server"
   pushes them to HestiaCP via `v-add-user-package` /
   `v-change-user-package-value`.
3. **Checkout**: plain `website_sale`. Confirming an order (which, on a
   real storefront, only happens after payment succeeds) creates:
   - a `contract.contract` with one recurring `contract.line` matching
     the package's price, billed monthly - `contract`'s own cron takes
     it from there for every renewal after the first.
   - a `hestiacp.account` record, immediately provisioned: creates the
     HestiaCP user, assigns the package, generates a random password
     and emails it (never stored in Odoo past that one message - see
     **Known simplifications** below).
4. **`hestiacp.account`** - the lifecycle tracker (`draft` → `active` →
   `suspended` → `terminated`), independent of any one order (a renewal
   invoice doesn't touch this record). A daily cron
   (`_cron_check_payment_status`) suspends an active account once its
   contract has an invoice unpaid past 7 days, unsuspends it once caught
   up, and terminates it (deletes the HestiaCP user) after 30 days
   suspended - not immediately, so a payment hiccup doesn't mean instant
   data loss.

## Setup

1. On HestiaCP: **Server → Access Keys** → create a key scoped to the
   `v-*` commands this module uses (`v-add-user`, `v-suspend-user`,
   `v-unsuspend-user`, `v-delete-user`, `v-change-user-password`,
   `v-change-user-package`, `v-add-user-package`,
   `v-change-user-package-value`, `v-list-user-packages`,
   `v-list-sys-info`). Whitelist the Odoo server's IP.
2. In Odoo: **Sales → Configuration → HestiaCP Servers** → add the
   server, then **Test Connection**.
3. Create a hosting product, tick **Hosting Package**, set the resource
   limits, pick the server, name the HestiaCP package, and **Sync
   Package to Server**.
4. Publish it on the website (`website_sale` as normal) and take a test
   order through checkout.

## Known simplifications / not yet built

- **No customer-chosen password at checkout.** The original scoping
  considered letting the customer set their own HestiaCP password
  during checkout; this build generates one and emails it instead - a
  standard, simpler pattern (and it's what most hosts already do for a
  first login). A password-reset self-service flow through the portal
  would be a good follow-up if a mailed password isn't desired
  long-term.
- **No portal "my hosting" page yet.** `hestiacp.account` has the
  record rule for it (portal users see only their own), but there's no
  actual portal controller/template surfacing account status or the
  control-panel link yet - next piece of work.
- **No automatic saved-card charge on renewal.** `contract`'s cron
  generates the renewal invoice; actually attempting to charge a saved
  Stripe token against it (rather than waiting for the customer to pay
  it manually, or an admin to trigger it) isn't wired up yet.
- **The exact HestiaCP API wire format (`models/hestiacp_api.py`) has
  not been checked against a live server.** It's built from HestiaCP's
  documented Access Key API conventions (POST to `/api/` with
  `access_key`/`secret_key`/`cmd`/`arg1..N`, `returncode=yes` appending
  the exit code as the last line), but this is the first thing to
  re-verify - and the only file that should need changing - once a real
  server is reachable. Same goes for the exact argument order HestiaCP
  expects for `v-add-user-package`/`v-change-user-package-value` in
  `product_template.py`'s `action_hestiacp_sync_package`.

## Testing

All business logic (provisioning, suspend/unsuspend/terminate, the
payment-status cron, the sale-order-confirmation hook) is covered by
tests that mock `hestiacp.server._get_client()` - nothing in the test
suite makes a real HTTP call. Run via this repo's `testing/` harness:

```
cd testing && ./pg_start.sh
python3 ~/dev/odoo-19/odoo-bin --addons-path=... -d hestiacp_test \
  -i hestiacp_hosting --test-enable --test-tags=/hestiacp_hosting \
  --stop-after-init --log-level=test
```
