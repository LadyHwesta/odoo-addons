# -*- coding: utf-8 -*-
{
    'name': 'Event Appearances',
    'version': '19.0.1.1.0',
    'category': 'Marketing/Events',
    'summary': "List events you're performing at, run by someone else: link to their tickets, show their flyer",
    'description': """
Event Appearances
=================

For performers, speakers and vendors who appear at events someone else
runs. Mark an event as an **appearance** and it's listed on your website
like your own events, but nothing is sold or registered in Odoo: the page
shows who's hosting, the host's flyer and materials, and a button to where
people buy tickets or register (or says entry is free).
""",
    'author': 'Meskis Works',
    'website': 'https://meskis.net',
    'license': 'LGPL-3',
    'images': ['static/description/banner.png'],
    'support': 'sales@meskis.net',
    'depends': ['website_event'],
    'data': [
        'views/event_event_views.xml',
        'views/website_event_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'website_event_appearance/static/src/scss/appearance.scss',
        ],
    },
    'installable': True,
}
