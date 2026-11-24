# Donations: Donor Covers the Fees

Adds an unticked **"I'll cover the processing fees (+$1.06) so the full gift
goes to …"** box to Odoo's own website Donation form (`website_payment`).
If the donor ticks it, the payment is grossed up so the organisation keeps
the whole gift after the card fees:

    total = (gift + fixed fee) / (1 - percentage)      rounded up to the cent

## Settings

Website > Configuration > Settings > Payments > **Donors Can Cover the Fees**:
on/off, the processing percentage (default 2.9%) and fixed amount (default
0.30), Stripe's standard US card rate. Other modules can add their own
percentage by extending `res.company._donation_cover_fee_rates()` (e.g.
`managed_odoo_stripe_connect_donation` adds Meskis' platform fee).

## How it works

- The box only previews the amount. `/donation/transaction` works it out
  again on the server from the gift and the company's rates, and creates
  the transaction for gift + fees; the browser's figure is never used.
- The gift and the fees covered are stored on the transaction
  (`donation_gift_amount`, `donation_fee_covered`) when it's created, before
  the payment provider is called, so providers and other modules can use
  them (`nonprofit_website_donation` puts them on the donation receipt).

## Testing

7 tests: the gross-up keeps the gift whole across amounts, the route
charges gift + fees only when ticked and enabled, and the form offers the
box unticked. Live-tested in the Stripe sandbox on 2026-11-24: a $25 gift
with the box ticked charged $26.33 (with a 1% platform fee added) and the
card form accepted the larger amount.
