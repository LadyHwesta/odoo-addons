# -*- coding: utf-8 -*-
{
    'name': 'Hosted Database Admin Guard',
    'version': '19.0.1.0.0',
    'category': 'Hidden/Tools',
    'summary': "Keep app installs and technical settings with the hosting provider",
    'description': """
Hosted Database Admin Guard
===========================

For a database someone else hosts. The customer's own administrators keep
Odoo's normal Settings role: company details, users and their access, and
every app's settings page. Only members of **Technical Administrator
(hosting provider)** can:

- install, remove or upgrade apps and modules, including through an app's
  settings page or the module wizards;
- open the Apps and Technical menus;
- write code: server actions and scheduled actions of type "Execute
  Code", and computed custom fields;
- change a technical administrator's login, password, email, groups or
  active status, or give anyone that role.

The built-in admin user becomes the technical administrator when this
module is installed.
""",
    'author': 'Meskis Works',
    'website': 'https://meskis.net',
    'license': 'LGPL-3',
    'depends': ['base'],
    'data': [
        'security/security.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
}
