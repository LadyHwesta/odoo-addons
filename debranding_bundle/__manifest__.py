# -*- coding: utf-8 -*-
{
    'name': 'Debranding Bundle',
    'version': '19.0.1.0.0',
    'category': 'Hidden/Tools',
    'summary': "One install for OCA's debranding: no Odoo online links, upsells or branding in emails and the portal",
    'description': """
Debranding Bundle
=================

Installs OCA's server-brand debranding modules together, so customers never
mistake the provider of their Odoo for Odoo S.A.: no Odoo online account
links, no Enterprise upsells in Settings, no "Powered by Odoo" in emails or
the portal. Two companion modules add the Sales portal and Website ones
automatically whenever Sales or Website is installed, now or later.
""",
    'author': 'Meskis Works',
    'website': 'https://meskis.net',
    'license': 'LGPL-3',
    'depends': ['disable_odoo_online', 'remove_odoo_enterprise', 'mail_debranding', 'portal_debranding'],
    'installable': True,
}
