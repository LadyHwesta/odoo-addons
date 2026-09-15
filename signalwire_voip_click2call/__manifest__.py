# -*- coding: utf-8 -*-
{
    'name': 'SignalWire Click-to-Call',
    'version': '19.0.1.0.0',
    'category': 'Productivity/VOIP',
    'summary': 'A real in-browser softphone (voip_oca) backed by SignalWire SIP Endpoints',
    'description': """
SignalWire Click-to-Call
=========================

Phase 2 of the SignalWire VoIP project. Bridges OCA's ``voip_oca`` (a
free, provider-agnostic SIP.js/WebRTC browser softphone) to SignalWire:

- One click provisions a user's own SignalWire "SIP Endpoint" and
  wires it into ``voip_oca``'s ``res.users`` VOIP settings - after
  that, that user has a real softphone (make/receive calls, click any
  partner's phone number, call log, missed-call activities) with no
  further setup.
- Assigning a purchased ``signalwire.phone_number`` to a user routes
  inbound calls to that number straight to their softphone, via a
  standard Twilio-compatible cXML ``<Dial><Sip>`` webhook.

See ``README.md`` for what's been live-verified and the one piece that
can't be verified from a script - actually placing/answering a call
needs a real browser.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['signalwire_voip', 'voip_oca'],
    'data': [
        'views/res_users_views.xml',
        'views/signalwire_phone_number_views.xml',
        'views/signalwire_server_views.xml',
    ],
    'installable': True,
    'application': False,
}
