# -*- coding: utf-8 -*-
{
    'name': 'POS Event Check-in',
    'version': '19.0.1.0.0',
    'category': 'Sales/Point of Sale',
    'summary': "Check people in at the door from the Point of Sale: scan their ticket or look them up",
    'description': """
POS Event Check-in
==================

Odoo's Point of Sale already sells event tickets at the door. This adds the
other half of the door: checking in people who bought tickets beforehand.
Scan a ticket (with a scanner or the device's camera) and it's checked in, with
the same rules as the Events app's Registration Desk; or open Check In to
look someone up by name, email or ticket number and see how many are in.
""",
    'author': 'Meskis Works',
    'website': 'https://meskis.net',
    'license': 'LGPL-3',
    'images': ['static/description/banner.png'],
    'support': 'sales@meskis.net',
    'depends': ['pos_event'],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_event_checkin/static/src/**/*',
        ],
    },
    'installable': True,
}
