# -*- coding: utf-8 -*-
{
    'name': 'Progressive Web App Icon (iOS + Visibility)',
    'version': '19.0.2.0.0',
    'category': 'Extra Tools',
    'summary': "Complete OCA's web_pwa_customize with iOS coverage and visible settings",
    'description': """
Progressive Web App Icon (iOS + Visibility)
=============================================

OCA's ``web_pwa_customize`` (from `OCA/web
<https://github.com/OCA/web>`_) lets you set a custom icon, short name,
and colors for Odoo's "Install app" prompt - but only for
``/web/manifest.webmanifest`` (Chrome, Edge, Android). It leaves two
things unsolved:

* **iOS Safari's "Add to Home Screen" never sees any of it** - Safari
  reads the ``apple-touch-icon`` link tag, not the PWA manifest, and
  ``web_pwa_customize`` doesn't touch that tag at all. Install from an
  iPhone and you still get Odoo's own stock icon.
* **Its own settings stay hidden** unless developer mode is on - it adds
  its fields to the existing "Progressive Web App" block in Settings >
  General Settings, but that block (along with core's pre-existing
  ``web.web_app_name`` field, which nothing else surfaces either) is
  gated behind ``base.group_no_one``.

This module (which depends on ``web_pwa_customize`` rather than
reimplementing icon storage) fixes both: it points the
``apple-touch-icon`` tag at whichever icon size ``web_pwa_customize``
already generated (falling back to Odoo's own artwork if none is set),
and removes the developer-mode restriction from the settings block -
General Settings already requires admin access, so this adds no real
exposure.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['web', 'base_setup', 'web_pwa_customize'],
    'data': [
        'views/res_config_settings_views.xml',
        'views/webclient_templates.xml',
    ],
    'installable': True,
    'application': False,
}
