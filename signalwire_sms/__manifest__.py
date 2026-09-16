# -*- coding: utf-8 -*-
{
    'name': 'SignalWire SMS',
    'version': '19.0.2.0.0',
    'category': 'Productivity/VOIP',
    'summary': 'Two-way SMS via SignalWire, chatter-logged against your own contacts',
    'description': """
SignalWire SMS
================

Phase 3 of the SignalWire VoIP project, built on ``signalwire_voip``'s
subproject/phone-number core: send/receive SMS with any contact from
Odoo, every message logging straight onto that partner's own chatter,
no new screen to learn. Genuinely generic - a customer's own separate
Odoo instance can install this directly to get real SMS through
whatever number(s) it has, not just Meskis Works' own team.

Each number also carries an optional forwarding webhook
(``sms_webhook_url``) - inbound messages get POSTed there as JSON too,
letting a number feed straight into another system alongside (or
instead of) Odoo's own chatter logging.

**Important, and outside this module's control**: as of December 2025,
newly purchased US numbers have no SMS capability at all until the
business completes SignalWire's Campaign Registry (10DLC) brand +
campaign registration.

2026-09-16: split out of this module's own reseller-only half - the
``/my/sms`` self-service portal, independently-usable customer API
token issuance, and everything else specific to running Meskis Works'
own reselling business now live in the private ``signalwire_voip_sale``
module (repo ``LadyHwesta/meskis-reseller-addons``). This module kept
only what's genuinely generic.
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
        'views/signalwire_sms_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
}
