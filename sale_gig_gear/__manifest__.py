# -*- coding: utf-8 -*-
{
    'name': 'Gig Gear Checklist',
    'version': '19.0.1.0.1',
    'category': 'Sales/Sales',
    'summary': "Your gear list, default gear per package, and a packing checklist on every gig",
    'description': """
Gig Gear Checklist
==================

Keep a list of your gear (speakers, lights, mics, cables...), say which gear
each package or add-on needs, and every confirmed gig gets its own packing
checklist. Tick items off as they go in the van; the load-in sheet prints the
list with boxes to tick on the day.
""",
    'author': 'Meskis Works',
    'website': 'https://meskis.net',
    'license': 'LGPL-3',
    'images': ['static/description/banner.png'],
    'support': 'sales@meskis.net',
    'depends': ['sale_gig_booking'],
    'data': [
        'security/ir.model.access.csv',
        'views/gig_gear_views.xml',
        'views/product_template_views.xml',
        'views/sale_order_views.xml',
        'report/gig_load_in_report.xml',
    ],
    'installable': True,
}
