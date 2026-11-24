# -*- coding: utf-8 -*-
{
    'name': 'Managed Odoo Stripe Connect - Donor-Covered Fees',
    'version': '19.0.1.0.0',
    'category': 'Hidden',
    'summary': "Donors who cover the fees also cover Meskis' fee; marks those payments for the bridge",
    'description': """
Links "Donations: Donor Covers the Fees" with payments through Meskis:

- the amount a donor adds also covers Meskis' fee (as the bridge reports it),
  so the organisation still receives the full gift;
- each such payment is marked for Meskis' bridge (Stripe metadata
  ``meskis_fee_covered`` and the gift in cents), which credits Meskis' share
  of it to the organisation's own hosting invoices.

Installs itself when both modules are present.
""",
    'author': 'Meskis Works',
    'website': 'https://meskis.net',
    'license': 'LGPL-3',
    'depends': ['managed_odoo_stripe_connect_client', 'website_donation_cover_fees'],
    'auto_install': True,
    'installable': True,
}
