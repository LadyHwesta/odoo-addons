# -*- coding: utf-8 -*-
{
    'name': 'VoIP Text Messages',
    'version': '19.0.2.4.0',
    'category': 'Productivity/VOIP',
    'summary': 'Two-way text messages with your contacts, logged on their chatter',
    'description': """
VoIP Text Messages
==================

Send and receive text messages with any contact from Odoo. Every
message is logged on that contact's chatter.

- Replies to STOP, HELP and START as the phone carriers require, and
  never texts a contact who has opted out.
- Delivery reports for sent texts.
- Optionally forward incoming texts to another system as well.

US numbers can only send texts once the business's texting
registration (10DLC) is approved. Setup notes are in ``README.md``.
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
