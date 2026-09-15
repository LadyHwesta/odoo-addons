# -*- coding: utf-8 -*-
{
    'name': 'Telehealth Booking',
    'version': '19.0.1.0.0',
    'category': 'Services/Appointment',
    'summary': 'A video tier per provider - Odoo\'s own video calling by default, an upgrade hook for something more',
    'description': """
Telehealth Booking
====================

A small, deliberately self-contained base: a **video tier** on each
provider (Basic/Premium) and one hook point
(``calendar.event._get_premium_video_url``) that a bridge module can
fill in. Installed alone, every booking uses Odoo's own built-in
Discuss video calling exactly as it already works today - nothing
about that behavior changes.

The point of splitting it this way: a provider who never needs more
than free, built-in video never has to install or configure anything
else. See ``telehealth_booking_signalwire``'s own README for the
premium tier this is designed to plug into, and this module's own
README for why Discuss alone has a real reliability ceiling worth
knowing about before promising it to paying patients.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['calendar', 'mail'],
    'data': [
        'views/res_users_views.xml',
        'views/calendar_event_views.xml',
    ],
    'installable': True,
    'application': False,
}
