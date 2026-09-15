# SignalWire VoIP Storefront

Phase 4 of the SignalWire VoIP project (see
[`signalwire_voip`](../signalwire_voip/) for Phase 1,
[`signalwire_voip_click2call`](../signalwire_voip_click2call/) for
Phase 2, and [`signalwire_sms`](../signalwire_sms/) for Phase 3). The
public storefront: a `/voip` search-and-buy page, real provisioning on
checkout, and **metered usage billing**.

## Setup

1. Create exactly one `product.template` with **VoIP Number** checked
   (its own "VoIP Number" product form page) and a SignalWire Account
   selected. Set its Sales Price to the flat monthly rental fee you
   want to charge (marked up over SignalWire's own ~$1/mo per-number
   cost) - the search page and checkout always use the first such
   product found.
2. On that `signalwire.server` record, set **Usage Markup %** (default
   20%) - applied over SignalWire's own real per-call/per-message cost
   when billing the second, metered contract line (see below).
3. Customers reach the search page at **`/voip`** (linked from the
   website's main menu as "Get a Phone Number").

## Billing design: one flat line, one metered line, real CDRs

Every purchase creates **one `contract.contract` with two lines**,
not one - the two parts of a real VoIP bill work fundamentally
differently:

1. **Number rental** - a flat monthly fee (the product's own Sales
   Price), `recurring_invoicing_type='pre-paid'` - identical in spirit
   to `hestiacp_hosting`'s and `namecheap_domains_sale`'s own
   recurring lines, since a number's rental cost really is fixed and
   known in advance.
2. **Metered usage** - `recurring_invoicing_type='post-paid'` (billed
   *after* the period ends, once the real cost is known - a metered
   line structurally cannot be billed in advance the way a flat fee
   can) and `is_signalwire_metered=True`. Its `price_unit` starts at
   `0.0` and is meaningless on its own - see the CDR mechanism below
   for how it actually gets priced.

**No new cron was needed for this** - `contract`'s own existing
recurring-invoice cron already calls `_prepare_invoice_line()` for
every due line regardless of what generates its price, so overriding
that one method is the entire mechanism. Unlike domain or hosting
renewal, there's also no separate "renew at the vendor" step needed -
SignalWire just keeps charging the underlying account for an owned
number automatically; Odoo's only job here is billing the customer for
it, not re-provisioning anything periodically.

## Real Call Detail Records, not a lump sum

The metered line's amount is **not** one opaque total. Every call and
SMS becomes its own persisted `signalwire.cdr` record, priced
individually:

- `contract.line._prepare_invoice_line()` calls
  `signalwire.subproject._sync_cdrs()`, which pulls this customer's
  calls + SMS for the exact period being invoiced (via `contract`'s
  own period-boundary logic, not reimplemented) and creates a
  `signalwire.cdr` for each one not already pulled (matched by
  SignalWire's own SID, so a record can never be double-billed).
- **The server's markup is applied per record**, not once over a
  total - each CDR gets its own `rate` (dollars/minute for a call, a
  flat per-message rate for SMS) and `billed_amount`, both already
  marked up. This is deliberate: a real phone bill's "rate" column
  shows what *the customer* was charged per unit, never the reseller's
  own wholesale cost - summing SignalWire's raw cost and marking up
  the total once would show the right total but never let a per-call
  rate be printed anywhere honestly.
- The metered line's `price_unit` is just the sum of that period's
  `signalwire.cdr.billed_amount` values.
- After the invoice is actually created, `contract.contract`'s own
  `_recurring_create_invoice` is overridden to link each of that
  period's CDRs to the resulting invoice line
  (`signalwire.cdr.move_line_id`/`move_id`) and generate a proper
  **itemized PDF phone bill** (`report/cdr_statement_templates.xml`) -
  account, invoice number, billing period, and a full call/message
  detail table (date, type, from, to, duration, rate, amount) -
  attached to the invoice. Usage never gets folded into the invoice as
  one line per call; the invoice itself always shows one clean summary
  line, with the real detail living in the attached statement, exactly
  like a real phone company's own bill.
- `signalwire.cdr` records are also browsable directly (Sales -> VoIP
  -> Call Detail Records) for auditing, independent of which invoice
  (if any) they ended up on.

## Checkout flow

On order confirmation, for every line carrying a `signalwire_phone_number`:

1. Find the customer's existing active `signalwire.subproject`, or
   create and provision a new one.
2. Purchase the chosen number into it
   (`signalwire.subproject.purchase_number` - real money, real trial
   credit, same as everywhere else in this project).
3. **Automatically issue a customer SMS access token**
   (`action_issue_customer_token`, from `signalwire_sms`) - so by the
   time the customer checks their portal page (`/my/sms`), their
   credentials are already waiting, no extra step needed on their
   side.
4. Create the two-line contract described above.

Click-to-call access (a SIP Endpoint / `voip_oca` softphone) is
**deliberately not bundled here** - that's a per-`res.users` thing
built for the business's own team in Phase 2, not something this
checkout flow provisions for a resold customer. Revisit if "also sell
browser-softphone access" becomes an actual product to offer.

## What this does NOT do

- **No suspend-for-non-payment.** An unpaid number-rental invoice
  doesn't release the number or otherwise restrict the account - known
  simplification, same category of gap `namecheap_domains_sale`
  accepts for a lapsed domain (it just doesn't get renewed) but
  arguably more consequential here since usage charges could keep
  accruing on a number nobody's paying for. Worth revisiting before
  this handles real paying customers at any volume.
- **No re-verification at add-to-cart.** Unlike
  `namecheap_domains_sale`'s domain search (which re-checks
  availability via `domains.check` before adding to cart),
  SignalWire's `AvailablePhoneNumbers` endpoint has no equivalent
  "is this one specific number still free" check to re-run - it's
  search-by-area-code only. The real, authoritative check happens
  where it has to: the actual purchase call at order confirmation. If
  someone else buys the exact same number in the (rare) window between
  add-to-cart and checkout completing, that purchase call raises
  *after* the customer's already been charged - not specially handled,
  same class of accepted risk as the domain storefront's own.
- **No pagination on usage lookups.** A subproject generating more
  than one page (50 records) of calls+messages in a single billing
  period would be undercounted - fine for a small reseller customer's
  actual volumes, not fine indefinitely.

## Not live-verified - blocked on the same two things flagged in Phase 3

- **The `price`/`from`/`to`/`start_time`/`date_sent` field shapes.**
  `_sync_cdrs` assumes standard (well-documented, not something this
  project needed to discover) Twilio-compatible field names - a
  lowercase `price` key holding a negative decimal string, `from`/`to`
  for the parties, `start_time`/`date_sent` for the timestamp - but the
  trial account has no billed usage yet to check any of this against
  for real (see `signalwire_sms`'s own README on the 10DLC/Campaign
  Registry gate blocking that). The real date-filter query params
  themselves (`StartTime>`/`<`, `DateSent>`/`<`) **were** live-verified
  - the API accepted them and returned a clean, correctly-shaped empty
  result, since no records exist yet to actually return. Confirm the
  record-level field names the moment real usage exists.
- **PDF generation itself.** `wkhtmltopdf` isn't installed in this dev
  environment, so `_render_qweb_pdf` couldn't be exercised for real -
  the underlying QWeb template *was* verified to render correctly as
  HTML (`_render_qweb_html`, no wkhtmltopdf needed), catching any
  template syntax problems, but the actual PDF conversion is
  unverified. Should just work on a real deployment (which will have
  wkhtmltopdf, same as any Odoo install that prints invoices at all).
- **A real end-to-end checkout.** Cart mechanics, contract creation,
  and the metered-billing/CDR/statement mechanism are all covered by
  mocked tests, but purchasing a real number through the actual
  website flow (rather than the model methods directly), then actually
  waiting for a real invoice with a real attached statement, hasn't
  been done yet - do that before trusting this in production, same
  discipline as every other storefront in this project.

## Testing

Cart line separation, order confirmation (subproject creation/reuse,
number purchase, token issuance, the two-line contract's own shape),
CDR pricing/per-record markup, the metered-billing
`_prepare_invoice_line` override, and the full
`_recurring_create_invoice` -> CDR-linking -> PDF-attachment flow
(with `_render_qweb_pdf` mocked, since this dev environment has no
`wkhtmltopdf`) are all covered. The QWeb statement template itself was
separately confirmed to render without error via `_render_qweb_html`.
Nothing in the automated suite makes a real HTTP call to SignalWire.
