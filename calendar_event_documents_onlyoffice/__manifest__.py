# -*- coding: utf-8 -*-
{
    'name': 'Calendar Meeting Documents: ONLYOFFICE',
    'version': '19.0.1.0.0',
    'category': 'Productivity/Calendar',
    'summary': 'Open meeting documents in ONLYOFFICE, and create a new agenda or minutes from a meeting',
    'description': """
On a meeting's Documents tab:

* **Open in ONLYOFFICE** on each document ONLYOFFICE can open (in the Odoo
  window or a new tab, per ONLYOFFICE's own setting).
* **New Agenda** and **New Minutes**: create a blank Word document named
  after the meeting, add it to the meeting's documents, and open it in the
  editor. Saving a new meeting happens first, automatically.

Needs ONLYOFFICE's own ``onlyoffice_odoo`` connector and a working
ONLYOFFICE Docs server.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['calendar_event_documents', 'onlyoffice_odoo'],
    'data': ['views/calendar_event_views.xml'],
    'auto_install': True,
    'installable': True,
    'application': False,
}
