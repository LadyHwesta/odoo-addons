# -*- coding: utf-8 -*-
{
    'name': 'SignalWire Voicemail to Project',
    'version': '19.0.1.0.0',
    'category': 'Productivity/VOIP',
    'summary': "Create or attach a project task straight from a voicemail",
    'description': """
SignalWire Voicemail to Project
====================================

Adds two actions to a voicemail record:

- **Create Task** - opens a pre-filled, unsaved ``project.task`` form
  for review (only offered when the caller matched a known contact).
  If that contact has exactly one project already flagged as theirs
  (``project.project.partner_id``), it's pre-filled too - two or more
  matches (or none) leave the Project field for a human to choose.
- **Attach to Project or Task** - a small wizard offering either an
  existing project or an existing task, narrowed to ones already
  flagged for the matched contact (the same lookup "Create Task"'s own
  smart default uses) - posts the recording + a chatter note
  immediately, no review step needed for logging onto an existing
  record.

Deliberately standalone - depends only on ``signalwire_voip_click2call``
and core ``project``, not on ``signalwire_voip_helpdesk_crm``, so
Project support installs on its own.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['signalwire_voip_click2call', 'project'],
    'data': [
        'security/ir.model.access.csv',
        'wizards/signalwire_voicemail_attach_project_wizard_views.xml',
        'views/signalwire_voicemail_views.xml',
    ],
    'installable': True,
    'application': False,
}
