# -*- coding: utf-8 -*-
{
    'name': 'SignalWire SMS',
    'version': '19.0.1.0.0',
    'category': 'Productivity/VOIP',
    'summary': 'Two-way SMS via SignalWire, for your own team and for resold customers',
    'description': """
SignalWire SMS
================

Phase 3 of the SignalWire VoIP project. Two related but separate
things, both built on ``signalwire_voip``'s subproject/phone-number
core:

- **Team messaging**: send/receive SMS with any contact from Odoo -
  every message logs straight onto that partner's own chatter, no new
  screen to learn.
- **Reselling SMS**: a customer's own subproject can be handed a real,
  independently-usable SignalWire API token (scoped to just messaging/
  numbers - see README for why this isn't the subproject's own,
  unretrievable auth_token), a simple portal page for the customer who
  prefers a UI over an API, and optional webhook forwarding of inbound
  messages into whatever system the customer already uses.

**Important, and outside this module's control**: as of December 2025,
newly purchased US numbers have no SMS capability at all until the
business completes SignalWire's Campaign Registry (10DLC) brand +
campaign registration - see README for what that means for both use
cases above before going live with either one.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['signalwire_voip', 'mail', 'portal', 'phone_validation'],
    'data': [
        'security/ir.model.access.csv',
        'security/signalwire_sms_security.xml',
        'wizards/signalwire_sms_compose_views.xml',
        'views/res_partner_views.xml',
        'views/signalwire_phone_number_views.xml',
        'views/signalwire_subproject_views.xml',
        'views/signalwire_sms_views.xml',
        'views/portal_templates.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
}
