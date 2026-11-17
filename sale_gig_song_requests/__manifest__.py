# -*- coding: utf-8 -*-
{
    'name': 'Gig Song Requests',
    'version': '19.0.1.1.0',
    'category': 'Sales/Sales',
    'summary': "Guests request songs from a QR code; clients set must-play and do-not-play lists in their portal",
    'description': """
Gig Song Requests
=================

Every booked gig gets a private song request page and a QR card to put on
the tables. Guests request a song from their phone; the page closes when the
gig ends. Before the gig, your client fills in must-play and do-not-play lists
from their customer portal. You see everything on the gig, mark requests
played or skipped, and anything on the do-not-play list is flagged.
""",
    'author': 'Meskis Works',
    'website': 'https://meskis.net',
    'license': 'LGPL-3',
    'images': ['static/description/banner.png'],
    'support': 'sales@meskis.net',
    'depends': ['sale_gig_booking', 'website'],
    'data': [
        'security/ir.model.access.csv',
        'views/gig_song_request_views.xml',
        'views/sale_order_views.xml',
        'views/website_templates.xml',
        'views/portal_templates.xml',
        'report/song_request_reports.xml',
    ],
    'external_dependencies': {'python': ['qrcode']},
    'post_init_hook': '_post_init_hook',
    'installable': True,
}
