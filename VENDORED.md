# Vendored OCA modules

Seven modules in this repo come from the **Odoo Community Association**, not from us:
`membership/`, `website_membership/`, `membership_prorate/`, `membership_withdrawal/`,
`contract/`, `contract_sale/`, `base_technical_features/`. The membership four are
vendored because the club suite (`club_membership` and friends) depends on them and
Odoo 19 dropped the core Membership app while OCA's proration / withdrawal add-ons
aren't on a 19.0 channel yet. `contract` and `contract_sale` are vendored because Odoo
CE has no recurring-billing app at all (`sale_subscription` is Enterprise-only) - they
back the HestiaCP hosting-billing build (`hestiacp_hosting`).
`base_technical_features` is vendored because editing things like email templates or
automated actions otherwise requires turning on developer mode every time - see its
own section below.

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

### `base_technical_features`

Source: <https://github.com/OCA/server-ux>

| Module | Upstream | Status |
| --- | --- | --- |
| `base_technical_features` | `19.0` @ `bc7bbaf` (2026-09-12) | **verbatim.** AGPL-3. Adds a "Technical feature" checkbox to user preferences - checking it gives that user permanent access to Settings > Technical menus (email templates, automated actions, etc.) without ever needing to turn on developer mode. Admin gets it automatically on install. |

Checked first whether this was even needed (per [[check-oca-before-building]]) rather
than building something from scratch: the *other* half of "editing automated messages
is hard" - not knowing Jinja placeholder syntax by hand - turned out to already be
solved natively in Odoo 19 core itself (`mail.template`'s Subject/Body fields use the
`web.DynamicPlaceholderPopover` widget, a proper searchable field picker), so nothing
needed building for that part at all. A related, older OCA module
(`email_template_configurator`, in `OCA/social`) that predated this native feature was
checked too and found abandoned - last existed on the `14.0` branch, dropped entirely
from `15.0` onward - too stale to consider porting for a problem Odoo core no longer
has.

Its own test suite passes in full (8/8) **but only when `web` is already installed
first** - a from-scratch single-shot `-i base_technical_features` (which only formally
depends on `base`) fails 4 of its own tests with `NotImplementedError: onchange() is
implemented in module 'web'`, because its tests use Odoo's `Form()` test helper, which
relies on an onchange implementation that actually lives in `web`. Not a bug in the
module - every real Odoo deployment always has `web` installed already - just a
same-pass test-harness ordering artifact, the same category as `contract`'s own CoA-
timing gotcha above. Install `web` first, or run in two passes, when testing locally.

## Updating / removing

When OCA publishes `membership_prorate` and `membership_withdrawal` on their own 19.0
branch, drop the ports here and depend on the upstream ones instead. The two ports are
worth submitting back upstream. `contract`/`contract_sale`/`base_technical_features`
need no porting - just pull a newer 19.0 commit if OCA ships fixes worth having.
