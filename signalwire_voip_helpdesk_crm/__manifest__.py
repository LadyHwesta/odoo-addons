# -*- coding: utf-8 -*-
{
    'name': 'SignalWire Voicemail to Helpdesk/CRM',
    'version': '19.0.1.0.0',
    'category': 'Productivity/VOIP',
    'summary': "Create or attach a helpdesk ticket, or a CRM lead, straight from a voicemail",
    'description': """
SignalWire Voicemail to Helpdesk/CRM
====================================

Adds three actions to a voicemail record:

- **Create Helpdesk Ticket** and **Attach to Existing Ticket** - only
  offered when the caller matched a known contact (there's no one to
  open a ticket against otherwise). Attaching lists that contact's own
  existing tickets to pick from.
- **Create Lead/Opportunity** - available either way.

Every action opens a pre-filled, unsaved form for review rather than
silently creating a finished record - fields like team, category, or
priority need a human's judgment, not a guess.

Depends on OCA's ``helpdesk_mgmt`` (Odoo's own ``helpdesk`` app is
Enterprise-only) and core ``crm``. See the README for setup.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['signalwire_voip_click2call', 'helpdesk_mgmt', 'crm'],
    'data': [
        'security/ir.model.access.csv',
        'wizards/signalwire_voicemail_attach_ticket_views.xml',
        'views/signalwire_voicemail_views.xml',
    ],
    'installable': True,
    'application': False,
}
