# -*- coding: utf-8 -*-
{
    'name': 'Helpdesk Customer Verification',
    'version': '19.0.1.0.1',
    'category': 'Services/Helpdesk',
    'summary': 'Customers prove who they are with a one-time support key before staff work on their account',
    'description': """
Helpdesk Customer Verification
==============================

Before a support agent discusses or changes a customer's account, the
customer proves who they are:

* **Support key:** the customer gets a one-time key from the customer portal
  (My Account > Support key), new on every request, valid for 30 minutes,
  and reads it to the agent.
* **Texted code:** when the customer can't reach the portal, the agent texts
  a 6-digit code to the account holder's mobile (with
  helpdesk_support_verification_sms).
* **Signed in:** a ticket a customer opens from the portal is verified
  already.

The agent types the key or code into Verify Customer on the ticket. Until a
ticket is verified (or marked as needing no account access, for general
questions), it can't move to a working stage. Only a keyed hash of each code
is stored; five wrong codes lock the ticket for 15 minutes.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['helpdesk_mgmt', 'portal'],
    'data': [
        'security/ir.model.access.csv',
        'views/helpdesk_ticket_views.xml',
        'views/portal_templates.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
}
