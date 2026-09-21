# -*- coding: utf-8 -*-
{
    'name': 'SignalWire Portal Support Calling',
    'version': '19.0.1.0.0',
    'category': 'Productivity/VOIP',
    'summary': 'Let portal customers request a support callback or place a live call - never an external one',
    'description': """
SignalWire Portal Support Calling
====================================

Extends ``signalwire_voip_click2call``'s internal call routing out to
the customer *portal* - an external contact can request a callback,
or (on a more advanced support tier) place a real live browser call
to reach a support agent directly, as an alternative to opening a
ticket or using Discuss.

- **Gated per contact**, with room for tiers: a new
  ``signalwire_portal_support_tier`` field on ``res.partner``
  (none/callback/live call). Enforced server-side on every route and
  RPC method, not just by hiding a button.
- **Never an external call**: the portal side can only ever reach a
  single, fixed internal "Portal Support" Call Group - there is no
  path, by design, for a portal visitor to dial an arbitrary number.
- **Callback requests** (Sub-phase 1, this version): submit a phone
  number and optional note; the SignalWire Receptionist group is
  notified live (the same bus mechanism the receptionist panel already
  uses) and can call back with one click from that same panel.
- Live browser-to-agent calling (Sub-phase 2) is a deliberately
  separate, not-yet-built follow-on - see the module's own README for
  the full design and what's genuinely new/unverified about it.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['signalwire_voip_click2call', 'portal'],
    'data': [
        'security/signalwire_callback_request_security.xml',
        'security/ir.model.access.csv',
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'signalwire_voip_portal/static/src/components/receptionist_panel/callback_requests.esm.js',
            'signalwire_voip_portal/static/src/components/receptionist_panel/callback_requests.xml',
        ],
    },
    'installable': True,
    'application': False,
}
