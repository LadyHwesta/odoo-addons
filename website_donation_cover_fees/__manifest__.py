# -*- coding: utf-8 -*-
{
    'name': 'Donor Covers the Fees',
    'version': '19.0.1.0.0',
    'category': 'Website/Website',
    'summary': "Let donors add the card processing fees to their gift, so the full gift arrives",
    'description': """
Donations: Donor Covers the Fees
================================

Adds an unticked "I'll cover the processing fees" box to the website's
donation form (Odoo's own Donation block). It shows the exact extra amount
for the gift chosen. If the donor ticks it, the payment is grossed up so
that, after the processing fees, the organisation receives the full gift.

The fee rates (a percentage and a fixed amount per payment) are set in
Website settings. The server always works out the amount itself; the
browser's figure is only for display. Each donation records the gift and
the fees covered separately, for receipts and reports.
""",
    'author': 'Meskis Works',
    'website': 'https://meskis.net',
    'license': 'LGPL-3',
    'images': ['static/description/banner.png'],
    'support': 'sales@meskis.net',
    'depends': ['website_payment'],
    'data': [
        'views/res_config_settings_views.xml',
        'views/payment_form_templates.xml',
        'views/payment_transaction_views.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'website_donation_cover_fees/static/src/interactions/cover_fees.js',
        ],
    },
    'installable': True,
}
