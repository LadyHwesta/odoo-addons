# -*- coding: utf-8 -*-
{
    'name': 'SignalWire VoIP',
    'version': '19.0.1.2.0',
    'category': 'Productivity/VOIP',
    'summary': 'Core SignalWire connector - projects, subprojects, phone numbers',
    'description': """
SignalWire VoIP
===============

Core connector for `SignalWire <https://signalwire.com/>`_, a Twilio-
API-compatible communications platform - foundation for reselling VoIP
service, click-to-call, and SMS built on top of it in separate modules.

This module alone provides:

- ``signalwire.server``: one project's connection settings (Space,
  Project ID, API Token) and a connection test.
- ``signalwire.subproject``: a provisioned container for one resold
  customer (a SignalWire "subproject"/subaccount) - subprojects share
  the parent project's balance, so this is about resource isolation
  (a customer's own numbers, calls, recordings), not separate billing.
- ``signalwire.phone_number``: search, purchase, and release phone
  numbers within a subproject.

See ``README.md`` for what's been live-verified against a real
SignalWire account and what hasn't yet.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['mail'],
    'data': [
        'security/ir.model.access.csv',
        'wizards/signalwire_phone_number_search_views.xml',
        'views/signalwire_server_views.xml',
        'views/signalwire_subproject_views.xml',
        'views/signalwire_phone_number_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
}
