# -*- coding: utf-8 -*-
{
    'name': 'Progressive Web App Icon',
    'version': '19.0.1.0.0',
    'category': 'Extra Tools',
    'summary': 'Use your own icon when Odoo is installed as an app',
    'description': """
Progressive Web App Icon
==========================

Odoo's "Install app" / "Add to Home Screen" icon (Chrome, Edge, Android,
iOS Safari) is hardcoded to Odoo's own artwork - there's no Settings
option to change it, even though the app's *name* already is one
(``web.web_app_name``) - it's just hidden behind developer mode, in a
"Progressive Web App" block nobody stumbles across.

This module surfaces that block unconditionally (no developer mode
needed - General Settings already requires admin access) and adds a
new field right next to the existing name one: **Settings > General
Settings > Progressive Web App**, upload your own square icon. Leave it
empty and the icon side of things changes nothing - Odoo's own icon is
still used everywhere.

Covers both places the icon is actually read from:

* the ``/web/manifest.webmanifest`` PWA manifest (Chrome/Edge/Android
  "Install app"),
* the ``apple-touch-icon`` link tag (iOS Safari "Add to Home Screen").

Your source image is resized on the fly for each size that's needed,
so one upload is enough - no need to prepare multiple pre-sized files.

**Not covered:** the small icon on the rarely-seen "you're offline"
page, which stays Odoo's own artwork. Low-traffic page, not worth the
extra complexity of caching a resized copy to a real static file for it.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['web', 'base_setup'],
    'data': [
        'views/res_config_settings_views.xml',
        'views/webclient_templates.xml',
    ],
    'installable': True,
    'application': False,
}
