# -*- coding: utf-8 -*-
{
    'name': 'eLearning: Performers Training',
    'version': '19.0.1.0.0',
    'category': 'Website/eLearning',
    'summary': "eLearning courses for the Performers Suite: bookings, gear and music, getting booked again",
    'description': """
eLearning: Performers Training
==============================

Three short courses (Odoo's eLearning app), ready on install, each with a quiz:

* **Bookings: From Request to Gig Day**: the Book a Date form, packages billed
  by the gig's hours, never booked twice, signature and deposit, the balance,
  the timeline and the Gig Sheet.
* **Gear and Music**: the gear list, packing, the client's must-play and
  do-not-play lists, song requests by QR code, and Songs to Get.
* **Getting Booked Again**: appearances at other people's events, Promote It,
  and the press kit page.

For salespeople (members only, by invitation).
""",
    'author': 'Meskis Works',
    'website': 'https://meskis.net',
    'license': 'LGPL-3',
    'depends': ['website_slides', 'sale_gig_gear', 'sale_gig_song_requests', 'website_press_kit',
                'website_event_appearance'],
    'data': ['data/slide_channel_data.xml'],
    'assets': {
        'web.assets_frontend': ['performers_elearning/static/src/scss/course_content.scss'],
    },
    'installable': True,
}
