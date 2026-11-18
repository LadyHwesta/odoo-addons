# -*- coding: utf-8 -*-
{
    'name': 'Debranding Bundle: Website',
    'version': '19.0.1.0.0',
    'category': 'Hidden/Tools',
    'summary': "Installs OCA's website debranding whenever Website is installed",
    'author': 'Meskis Works',
    'website': 'https://meskis.net',
    'license': 'LGPL-3',
    'depends': ['debranding_bundle', 'website', 'website_debranding'],
    # Installs itself (and website_debranding) as soon as Website is there.
    'auto_install': ['debranding_bundle', 'website'],
    'installable': True,
}
