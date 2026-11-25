# -*- coding: utf-8 -*-
{
    'name': 'eLearning: Performer Events Training',
    'version': '19.0.1.1.2',
    'category': 'Website/eLearning',
    'summary': "eLearning course for Performer Events: paying performers and staff, and the door",
    'description': """
eLearning: Performer Events Training
====================================

One short course (Odoo's eLearning app) with a quiz, ready on install:
**Your Own Events: Paying Talent and the Door**: performer fees and staff
hours billed as draft vendor bills (1099-NEC ready), and checking people in
at the door from the Point of Sale.

For event users (members only, by invitation).
""",
    'author': 'Meskis Works',
    'website': 'https://meskis.net',
    'license': 'LGPL-3',
    'depends': ['website_slides', 'website_slides_publication_digest', 'event_performer_payout', 'pos_event_checkin'],
    'data': ['data/slide_channel_data.xml'],
    'assets': {
        'web.assets_frontend': ['performers_elearning_events/static/src/scss/course_content.scss'],
    },
    'installable': True,
}
