# -*- coding: utf-8 -*-
{
    'name': 'Helpdesk Customer Verification: Texted Codes',
    'version': '19.0.1.0.0',
    'category': 'Services/Helpdesk',
    'summary': "Text a one-time code to the account holder's mobile when they can't reach the portal",
    'description': """
Helpdesk Customer Verification: Texted Codes
============================================

Adds the backup for Helpdesk Customer Verification: when a customer can't
sign in to the portal for a support key, the agent texts a 6-digit code to
the mobile number on their account, and the customer reads it back.

* Codes go to the contact's **Mobile for Support Codes**, or their phone
  number when that is empty, from the number chosen in Settings > Helpdesk.
* A code works once, for 10 minutes. At most 3 can be sent per contact per
  hour.
* The code itself is never stored or shown in the chatter: the log says a
  code was sent, not what it was.
* Contacts who replied STOP can't be texted; use their support key instead.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['helpdesk_support_verification', 'signalwire_sms'],
    'data': ['views/views.xml'],
    'auto_install': True,
    'installable': True,
    'application': False,
}
