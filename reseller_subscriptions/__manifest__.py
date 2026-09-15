# -*- coding: utf-8 -*-
{
    'name': 'Reseller Subscriptions',
    'version': '19.0.1.0.0',
    'category': 'Sales/Subscriptions',
    'summary': 'One self-service "My Subscriptions" hub across hosting, domains, and SignalWire telecom',
    'description': """
Reseller Subscriptions
=======================

Meskis Works sells three independent recurring services out of this
Odoo - web hosting (``hestiacp_hosting``), domain registration/renewal
(``namecheap_domains_sale``), and VoIP/SMS/video
(``signalwire_voip_sale``, ``signalwire_sms``,
``telehealth_booking_signalwire``). Each already bills through the
same vendored OCA ``contract`` engine, but a customer using more than
one has no single place to see or manage what they've got - and
SignalWire's own billing had a real gap (see below).

This module adds:

- **One unified self-service portal page**, ``/my/subscriptions`` -
  every subscription across all three lines in one list, with real
  self-service actions (change package, cancel, stop renewing,
  release a number) and a shared "apply a saved card" action, instead
  of three separate (or, for domains and SignalWire billing, entirely
  missing) portal experiences.
- **Closes a real billing gap in SignalWire**: a purchased phone
  number's contract was created at checkout but never linked back to
  it anywhere, so nothing ever auto-charged a SignalWire customer's
  saved card, and releasing a number never stopped its billing. Both
  fixed here, additively - ``signalwire.phone_number`` gains
  ``contract_id``/``payment_token_id`` and a proper auto-charge cron.
- **A "stop renewing" action for domains**, which had none before -
  domains could be registered and renewed, but never explicitly
  cancelled.

Deliberately does NOT touch ``hestiacp_hosting`` or
``namecheap_domains_sale``'s own existing billing code - both are
already live in production and already working; everything here is
either purely additive (new fields/methods via ``_inherit``) or a new
aggregation layer built on top. See README.md for the full design,
including what's scoped for a later phase (billing a whole managed
Odoo instance as a product) rather than attempted here.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': [
        'contract', 'contract_sale', 'payment', 'account_payment', 'portal',
        'hestiacp_hosting', 'namecheap_domains_sale', 'signalwire_voip_sale',
        'signalwire_voip', 'signalwire_sms', 'telehealth_booking_signalwire',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/portal_templates.xml',
    ],
    'installable': True,
    'application': False,
}
