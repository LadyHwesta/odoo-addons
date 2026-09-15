# -*- coding: utf-8 -*-
{
    'name': 'SignalWire 10DLC Registration',
    'version': '19.0.1.0.0',
    'category': 'Productivity/VOIP',
    'summary': 'Self-service A2P 10DLC brand/campaign registration for resold SignalWire numbers',
    'description': """
SignalWire 10DLC Registration
================================

Every US carrier requires a registered "brand" (business identity) and
"campaign" (messaging use case) with The Campaign Registry before a
number can send A2P SMS - confirmed the hard way: a real send attempt
from an unregistered number came back
``421717 - "From must belong to an active campaign."`` Every resold
SignalWire customer hits this same wall on their own numbers, not just
the business's own.

Automates the real registration flow via SignalWire's own Registry API
(``SignalWireClient.registry_get``/``registry_post``, added in
``signalwire_voip``) - confirmed live 2026-09-15 against the user's
own account: brands and campaigns live flat at the top-level account
(no subaccount scoping exists), and a specific phone number gets tied
to a specific campaign via an "order" addressed directly by
``campaign_id``, referencing that number's own SID.

- ``signalwire.brand`` - one per resold customer's real business
  identity (never the reseller's own).
- ``signalwire.campaign`` - one messaging use case per brand, billed
  monthly through ``reseller_subscriptions``'s own
  ``contract.billing.mixin``, with a 3-month minimum commitment.
- ``signalwire.phone_number`` gains ``campaign_id`` and a self-service
  "Enable SMS" action - opt-in per number, not automatic at checkout.

Self-service throughout (extends ``signalwire_sms``'s own ``/my/sms``
portal) - the customer is the one certifying their own business
identity, so they're the one who fills in the form.

Not live-tested with a real brand/campaign submission - that needs
real customer business data and incurs real, non-refundable
registration cost. See README.md.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['signalwire_sms', 'signalwire_voip', 'reseller_subscriptions'],
    'data': [
        'security/ir.model.access.csv',
        'security/signalwire_10dlc_security.xml',
        'data/product_template_data.xml',
        'data/ir_cron_data.xml',
        'views/signalwire_brand_views.xml',
        'views/signalwire_campaign_views.xml',
        'views/portal_templates.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
}
