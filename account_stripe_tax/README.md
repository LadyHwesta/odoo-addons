# Sales Tax from Stripe Tax (`account_stripe_tax`)

Odoo creates and sends the invoices; [Stripe Tax](https://docs.stripe.com/tax)
works out the US sales tax (or VAT/GST) for each customer's address.

## How it works

1. Each product that should be taxed this way has a **Stripe Tax Code**
   (product form, next to Customer Taxes). Examples:
   - `txcd_10103001` SaaS, business use
   - `txcd_10701100` website hosting
   - [full list](https://docs.stripe.com/tax/tax-codes)

   Products without a code are never touched (domains, setup fees, phone
   service, anything you tax by hand).
2. Confirming a customer invoice sends its coded lines (amount after
   discount, tax code, reference) and the customer's address (delivery
   address if different, else invoicing address) to
   `POST /v1/tax/calculations`, expanding each line's tax breakdown.
3. Each line gets an ordinary Odoo percentage tax at the rate Stripe
   returned ("Sales Tax 9.25%", made on first use, posting to the Sales Tax
   Account in Settings). Your other taxes on the line are kept. A zero rate
   (another state, an exempt customer) leaves no Stripe tax on the line.
4. After posting, the sale is recorded in Stripe with
   `create_from_calculation`, so Stripe's reports match. Only taxed sales are
   recorded unless **Record untaxed sales** is on (see Cost).
5. A credit note on a recorded invoice reverses it in Stripe: fully when it
   credits the whole invoice, otherwise by its total (`flat_amount`).
   Resetting a recorded invoice to draft reverses it too; confirming again
   records it afresh (references stay unique, as Stripe requires).

## When things go wrong

- **No country, or a US/Canadian customer without a ZIP**: the invoice can't
  be confirmed until the address is fixed. Tax depends on it.
- **Stripe refuses or is unreachable while calculating**: that invoice
  stays draft with Stripe's message. Nothing else is affected.
- **Recording fails after the invoice is confirmed**: the invoice stays
  confirmed (the tax on it is already right), gets a note, a "Record in
  Stripe Tax" to-do, and a **Record in Stripe Tax** button to retry.

## Setup

1. Stripe Dashboard: turn on Stripe Tax, set your origin address, and add
   your registrations (Stripe returns zero tax where you aren't registered).
2. Odoo: the Stripe payment provider must have its secret key.
   Accounting > Configuration > Settings > Taxes > **Stripe Tax**: pick
   the Stripe account and your sales-tax payable account.
3. Put Stripe tax codes on the products to tax. Mark exempt customers
   (Accounting tab: **Exempt from Sales Tax**) and keep their certificates.

Test mode: with the provider in Test state its test key is used, so test
registrations and calculations don't cost anything.

## Cost (Stripe Tax Basic, API integration)

50¢ per recorded transaction where you're registered, including 10
calculations; 5¢ per extra calculation. No monthly fee. With **Record
untaxed sales** off (default), untaxed invoices aren't recorded, which saves
the fee but means Stripe's threshold monitoring only sees taxed sales; turn
it on if you get near another state's threshold. Filing returns needs Stripe
Tax Complete (from $90/month); on Basic you file using Stripe's reports.

## Notes

- API calls send no `Stripe-Version` header: Odoo's Stripe module pins a
  2019 version, older than Stripe Tax, so the account's default is used.
- Telecom surcharges (911, 988, CPUC PPP) aren't sales tax and aren't
  handled by Stripe Tax; use fixed Odoo taxes for those.
- Lines with a zero or negative amount aren't sent and get no sales tax.
- Rounding: Odoo computes the tax from the rate per line, which can differ
  from Stripe's own per-line rounding by a cent.
