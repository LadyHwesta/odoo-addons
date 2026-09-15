# -*- coding: utf-8 -*-
{
    'name': 'SignalWire VoIP Storefront',
    'version': '19.0.1.0.0',
    'category': 'Sales',
    'summary': 'Sell VoIP numbers through the website, billed on real metered usage',
    'description': """
SignalWire VoIP Storefront
============================

Phase 4 of the SignalWire VoIP project (see ``signalwire_voip``,
``signalwire_voip_click2call``, and ``signalwire_sms`` for Phases 1-3).
A ``/voip`` website page where a customer searches for and buys a
phone number, real provisioning on checkout (a SignalWire subproject +
the purchased number + an SMS access token), and **metered usage
billing** - a flat monthly number-rental fee plus a variable line
priced by summing real, per-record Call Detail Records (calls + SMS),
each individually marked up so it carries a genuine customer-facing
rate. Every metered invoice gets a proper itemized PDF phone bill
attached (date/type/from/to/duration/rate/amount per call or message)
rather than folding usage into the invoice as one line per call.

See ``README.md`` for the billing design, what's live-verified, and -
importantly - the real compliance gate (10DLC/Campaign Registry) that
blocks any of this from actually carrying live SMS traffic yet.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': [
        'signalwire_voip', 'signalwire_sms', 'sale_management', 'website_sale',
        'payment', 'account_payment', 'contract', 'contract_sale',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/product_signalwire_usage_data.xml',
        'report/cdr_statement_templates.xml',
        'views/product_template_views.xml',
        'views/voip_search_templates.xml',
        'views/signalwire_cdr_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'signalwire_voip_sale/static/src/js/voip_search.js',
        ],
    },
    'installable': True,
    'application': False,
}
