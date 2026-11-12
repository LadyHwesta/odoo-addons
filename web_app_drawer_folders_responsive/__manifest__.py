# -*- coding: utf-8 -*-
{
    'name': 'App Drawer Folders: Full-Screen Grid',
    'version': '19.0.1.0.0',
    'category': 'Hidden/Tools',
    'summary': "Folder headings in web_responsive's full-screen app grid",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['web_app_drawer_folders', 'web_responsive'],
    'assets': {
        'web.assets_backend': [
            'web_app_drawer_folders_responsive/static/src/apps_menu.xml',
            'web_app_drawer_folders_responsive/static/src/apps_menu.scss',
        ],
    },
    'auto_install': True,
    'installable': True,
}
