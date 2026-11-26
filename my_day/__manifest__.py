# -*- coding: utf-8 -*-
{
    'name': 'My Day',
    'version': '19.0.1.2.0',
    'category': 'Productivity',
    'summary': "A start screen to plan and work through your day, across your companies and branches",
    'description': """
My Day
======

A start screen for the working day: today's calendar, your to-dos, calls and
texts to answer on one side, what needs attention on the other (threat
status for security officers, tickets, leads, tasks coming due, money owed
and due, quotes waiting on customers, this week's events). Each section has
its own colour, and everyone can pick a background picture or upload their
own. It follows the
company switcher, so with several companies or branches selected you see
them all, marked by company. Tick "Start on My Day" in your preferences to
open it after login. The My Day tab in Preferences lets everyone choose which
sections to show, their order and column, how many items each lists, and
options like how far ahead to look.

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
        'security/ir.model.access.csv',
        'security/my_day_security.xml',
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
