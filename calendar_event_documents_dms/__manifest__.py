# -*- coding: utf-8 -*-
{
    'name': 'Calendar Meeting Documents: Link from Documents',
    'version': '19.0.1.1.0',
    'category': 'Productivity/Calendar',
    'summary': 'Link files from a DMS folder (e.g. a team folder) to a meeting instead of copying them',
    'description': """
Adds **Linked Files** to a meeting's Documents tab: pick files from OCA
``dms`` (for example a team folder), so the meeting points at the same
file everyone edits, rather than a copy. Opening one opens it in
Documents (and from there in ONLYOFFICE, when installed). Access stays
the folder's: attendees who can't open that folder can't open the file.
Linked files kept as attachments (Attachment storage, as team folders are)
also go out with invitations.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['calendar_event_documents', 'dms'],
    'data': ['views/calendar_event_views.xml'],
    'auto_install': True,
    'installable': True,
    'application': False,
}
