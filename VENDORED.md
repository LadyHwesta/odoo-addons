# Vendored OCA modules

Six modules in this repo come from the **Odoo Community Association**, not from us:
`membership/`, `website_membership/`, `membership_prorate/`, `membership_withdrawal/`,
`contract/`, `contract_sale/`. The membership four are vendored because the club suite
(`club_membership` and friends) depends on them and Odoo 19 dropped the core Membership
app while OCA's proration / withdrawal add-ons aren't on a 19.0 channel yet. `contract`
and `contract_sale` are vendored because Odoo CE has no recurring-billing app at all
(`sale_subscription` is Enterprise-only) - they back the HestiaCP hosting-billing build
(`hestiacp_hosting`).

Each keeps **its own upstream licence** (see the module's `__manifest__.py`) - they
are *not* covered by the repo's top-level LGPL-3.

They sit at the repo root next to our own modules (they were briefly under a
`vendor/oca/` subdir - that broke Bootstrap's `@import "vendor/rfs"` because Odoo's
SCSS importer resolves `file_path("vendor")` to any top-level `vendor` dir on the
addons path before Bootstrap's own `scss/vendor/`). Nothing extra to add to
`addons_path` - the repo root is enough.

## Contents

Source: <https://github.com/OCA/vertical-association>

| Module | Upstream | Status |
| --- | --- | --- |
| `membership` | `19.0` @ `8153173` (2026-08-11) | **verbatim.** Odoo removed the classic Membership app in 19.0; this is OCA's re-port. LGPL-3. |
| `website_membership` | `19.0` @ `8153173` | **verbatim.** Opt-in public member directory. LGPL-3. |
| `membership_prorate` | `18.0` @ `0f311b4` (2026-07-27) | **ported 18.0 → 19.0.** AGPL-3. Change: `membership.membership_line.account_invoice_line` → `account_invoice_line_id` (renamed in `membership` 19.0); tests rebased onto `membership`'s `AccountTestInvoicingCommon`. |
| `membership_withdrawal` | `18.0` @ `0f311b4` | **ported 18.0 → 19.0.** AGPL-3. Changes: `depends` `membership_extension` → `membership` (19.0 base absorbed it); `member_lines` → `member_line_ids`, `associate_member` → `associate_member_id`, `fields.first()` → `[:1]`; merged the two partner-form inherits into one. |

`membership_extension` (18.0) was **not** brought over - the `membership` 19.0 module
already includes everything it did (categories, editable membership lines, state
decoupled from the invoice, adhered/associate members, the expiry cron).

`readme/` fragment dirs, `pyproject.toml` packaging files, and `i18n/` translation
catalogues (~250 `.po` files; the club runs in English, pull a language from upstream
if needed) were stripped from the copies. Nothing else in the verbatim modules was
touched.

### `contract` / `contract_sale`

Source: <https://github.com/OCA/contract>

| Module | Upstream | Status |
| --- | --- | --- |
| `contract` | `19.0` @ `de43ca0` (2026-09-12) | **verbatim.** AGPL-3. Recurring contracts + invoice generation cron - the actual recurring-billing engine. |
| `contract_sale` | `19.0` @ `de43ca0` | **verbatim.** AGPL-3. Links a `sale.order` to a `contract.contract`. |

Both are on a real, actively-maintained 19.0 branch already, so - unlike the
membership proration/withdrawal ports above - no porting was needed, just a plain
copy (same `readme/`/`pyproject.toml`/`i18n/` stripping as the membership modules).
Their own OCA test suites pass in full (72/72) against this repo's local harness,
**but only when a chart of accounts already exists before installing them** - a
from-scratch single-shot `-i contract,contract_sale` fails most of `contract`'s own
tests with "Please define a sale journal," because the demo company's CoA is set up
by `account`'s `post_init_hook`, which runs *after* `at_install` tests for modules
loaded earlier in the graph - not a bug in the module. Install `sale` (or any
localization module) first, or run in two passes, when testing locally.

`contract_payment_mode` (auto-installed by nothing, needs OCA's separate
`account_payment_mode` plus the `openupgradelib` Python package) was **not** vendored
- the hosting-billing module handles charging a saved Stripe token directly rather
than going through OCA's payment-mode abstraction.

## Updating / removing

When OCA publishes `membership_prorate` and `membership_withdrawal` on their own 19.0
branch, drop the ports here and depend on the upstream ones instead. The two ports are
worth submitting back upstream. `contract`/`contract_sale` need no porting - just pull
a newer 19.0 commit if OCA ships fixes worth having.
