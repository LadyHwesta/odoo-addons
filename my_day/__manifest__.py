# -*- coding: utf-8 -*-
{
    'name': 'My Day',
    'version': '19.0.1.0.0',
    'category': 'Productivity',
    'summary': "A start screen to plan and work through your day, across your companies and branches",
    'description': """
My Day
======

A start screen for the working day: today's calendar and your to-dos on one
side, what needs attention on the other (tasks coming due, money owed and
due, quotes waiting on customers, this week's events). It follows the
company switcher, so with several companies or branches selected you see
them all, marked by company. Tick "Start on My Day" in your preferences to
open it after login.

Sections only appear for apps you have installed and are allowed to see.
Other modules can add their own sections.
""",
    'author': 'Meskis Works',
    'website': 'https://meskis.net',
    'license': 'LGPL-3',
    'images': ['static/description/banner.png'],
    'support': 'sales@meskis.net',
    'depends': ['mail', 'calendar'],
    'data': [
        'views/my_day_views.xml',
        'views/res_users_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'my_day/static/src/my_day/*',
        ],
    },
    'application': True,
    'installable': True,
}
