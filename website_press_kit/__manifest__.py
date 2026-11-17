# -*- coding: utf-8 -*-
{
    'name': 'Website Press Kit',
    'version': '19.0.1.0.0',
    'category': 'Website/Website',
    'summary': "A press kit page for performers and artists: bio, photos to download, links, upcoming shows",
    'description': """
Website Press Kit
=================

One press kit page per website, for promoters, venues and journalists:
your bio, genres and where you're based, photos they can download in full
size, links to mixes, videos and socials, a technical rider, your upcoming
events (live from your events, including appearances at other people's
events), and a button to book you. Edited in Website > Site >
Press Kit, laid out with your website's own theme.
""",
    'author': 'Meskis Works',
    'website': 'https://meskis.net',
    'license': 'LGPL-3',
    'images': ['static/description/banner.png'],
    'support': 'sales@meskis.net',
    'depends': ['website_event'],
    'data': [
        'security/ir.model.access.csv',
        'views/press_kit_views.xml',
        'views/press_kit_templates.xml',
    ],
    'installable': True,
}
