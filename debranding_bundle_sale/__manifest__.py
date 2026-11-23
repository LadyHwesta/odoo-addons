# -*- coding: utf-8 -*-
{
    'name': 'Debranding Bundle: Sales',
    'version': '19.0.1.0.0',
    'category': 'Hidden/Tools',
    'summary': "Installs OCA's Sales portal debranding whenever Sales is installed",
    'author': 'Meskis Works',
    'website': 'https://meskis.net',
    'license': 'LGPL-3',
    'depends': ['debranding_bundle', 'sale', 'sale_portal_debranding'],
    # Installs itself (and sale_portal_debranding) as soon as Sales is there.
    'auto_install': ['debranding_bundle', 'sale'],
    'installable': True,
}
