# -*- coding: utf-8 -*-
{
    "name": "Sales Tax from Stripe Tax",
    "version": "19.0.1.0.0",
    "category": "Accounting/Accounting",
    "summary": "Customer invoices get the right sales tax for each address from Stripe Tax",
    "description": """
Sales Tax from Stripe Tax
=========================

Odoo creates the invoice; Stripe Tax works out the sales tax.

* Each product carries a **Stripe tax code** (e.g. ``txcd_10103001`` for
  business SaaS). Products without one are never taxed by this module.
* When a customer invoice is confirmed, Odoo sends its taxable lines and
  the customer's address to Stripe's Tax Calculation API and puts the
  rate Stripe returns on each line, as an ordinary Odoo tax posting to
  your sales-tax account. Rates are created as needed ("Sales Tax
  9.25%").
* The sale is then recorded in Stripe Tax, so Stripe's reports and
  threshold monitoring see it. Credit notes and invoices reset to draft
  are reversed there.
* Customers can be marked tax-exempt.

Uses the API key of your Stripe payment provider. Stripe only charges
tax where you've added a registration in its dashboard. See README.md.
""",
    "author": "Tiesa",
    "license": "LGPL-3",
    "website": "https://github.com/LadyHwesta/odoo-addons",
    "depends": ["account", "payment_stripe"],
    "data": [
        "views/res_config_settings_views.xml",
        "views/product_template_views.xml",
        "views/res_partner_views.xml",
        "views/account_move_views.xml",
    ],
    "installable": True,
    "application": False,
}
