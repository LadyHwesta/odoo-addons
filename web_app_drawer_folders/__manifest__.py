# -*- coding: utf-8 -*-
{
    'name': 'App Drawer Order and Folders',
    'version': '19.0.1.0.0',
    'category': 'Hidden/Tools',
    'summary': 'Put apps in your own order and group them into folders, and keep it through upgrades',
    'description': """
App Drawer Order and Folders
============================

Settings > Users & Companies > App Drawer:

* **Apps**: drag every app into the order you want, and put apps in
  folders. Apps outside a folder come first.
* **Folders**: name them ("Money", "Phones", "Events") and drag them into
  order.

The order and folders are kept in their own records, so module upgrades
(which reset each menu's own sequence) don't undo them.

The order applies everywhere apps are listed. Folder headings appear in
OCA's ``web_responsive`` full-screen app grid
(``web_app_drawer_folders_responsive`` installs itself) and in the apps
dropdown signed-in staff see on website pages
(``web_app_drawer_folders_website``). Odoo's plain dropdown, used only
without ``web_responsive``, gets the order but no headings:
``web_responsive`` replaces that dropdown outright, so changing it from
here would break the backend whenever both are installed (found in
testing).
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['web'],
    'data': [
        'security/ir.model.access.csv',
        'views/app_drawer_views.xml',
    ],
    'installable': True,
    'application': False,
}
