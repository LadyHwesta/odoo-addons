# -*- coding: utf-8 -*-
{
    'name': 'DMS Team Folders',
    'version': '19.0.1.0.0',
    'category': 'Productivity/Documents',
    'summary': 'Shared DMS folders for a team, with real member-only access',
    'description': """
DMS Team Folders
================

Shared folders for a team or a group of people, not tied to a contact or any
other business record. Each folder has members, who can add and edit files, and
viewers, who can only read them. Everyone else can't reach the files, in DMS or
through the attachment behind them.

Files are stored as attachments, so with ``dms_onlyoffice`` installed they can
be edited in ONLYOFFICE as well.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['dms'],
    'data': [
        'security/dms_team_folder_security.xml',
        'security/ir.model.access.csv',
        'data/dms_team_folder_data.xml',
        'views/dms_team_folder_views.xml',
    ],
    'installable': True,
    'application': False,
}
