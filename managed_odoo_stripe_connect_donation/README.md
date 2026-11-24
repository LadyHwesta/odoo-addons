# Managed Odoo Stripe Connect: Donor-Covered Fees

Glue between `website_donation_cover_fees` and
`managed_odoo_stripe_connect_client`, installed automatically when both are.

- `res.company._donation_cover_fee_rates()` adds Meskis' fee
  (`stripe_connect_fee_percent`, from the bridge's checkout config, refreshed
  daily) when the company takes payments through Meskis, so a donor covering
  the fees covers Meskis' fee too and the full gift still arrives.
- `_stripe_prepare_payment_intent_payload()` marks a fee-covered donation with
  Stripe metadata `meskis_fee_covered=1` and `gift_amount` (cents). Meskis'
  bridge credits its fee on those payments to the organisation's own invoices
  (`managed_odoo_stripe_connect`, `stripe.connected_account.credit`).

6 tests. Live-tested in the Stripe sandbox on 2026-11-24 ($25 gift, $26.33
charged, 26¢ fee credited by the bridge).
