# -*- coding: utf-8 -*-
{
    'name': 'Reload After Upgrades',
    'version': '19.0.1.0.0',
    'category': 'Extra Tools',
    'summary': 'Open Odoo windows and installed apps reload themselves after a server upgrade',
    'description': """
Reload After Upgrades
=====================

After the server's modules are upgraded, a window that was already open
keeps running the old screens until someone reloads it. In the installed
app (PWA) there is often no reload button, so people end up quitting and
reopening the app.

This module compares the window's registry fingerprint with the
server's whenever the window comes back to the front, the live
connection reconnects (as it does after a restart) and every ten
minutes. When they differ, it saves the open record, clears the
browser caches and reloads. If something can't be saved, or a dialog is
open, it asks instead.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'support': 'sales@meskis.net',
    'images': ['static/description/banner.png'],
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['web', 'bus'],
    'assets': {
        'web.assets_backend': [
            'web_reload_on_upgrade/static/src/reload_on_upgrade_service.js',
        ],
    },
    'installable': True,
    'application': False,
}
