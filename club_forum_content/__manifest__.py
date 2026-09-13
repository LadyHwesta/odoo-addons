# -*- coding: utf-8 -*-
{
    'name': 'Club Forum Content',
    'version': '19.0.1.1.0',
    'category': 'Website',
    'summary': "Recreates the club's WordPress (bbPress) forum history in website_forum",
    'description': """
Club Forum Content
====================

Recreates the club's old WordPress forum (bbPress plugin, at
sonomacountyradioamateurs.com/wp/forums/) as Odoo ``website_forum``
data - 3 categories and their topic/reply history.

**Attribution note**: historical posts are attributed to a single
"Forum Archive Import" system user rather than individually-created
accounts for every original poster (~80+ distinct people). Each
imported post's body is prefixed with the real original author's name
and posting date as plain text, so that information isn't lost - it
just isn't a clickable profile link the way a live Odoo user would be.
If a poster turns out to already be a real member with their own Odoo
login, re-attributing their specific posts by hand afterward is
possible but not done automatically here.

Original post/reply timestamps *are* preserved on ``create_date``
(Odoo's own field-loading code allows this specifically during module
installation), so the forum's history reads in its real chronological
order rather than everything dated "today."
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['website_forum'],
    'data': [
        'data/forum_categories.xml',
        'data/topics_activities.xml',
        'data/topics_announcements.xml',
        'data/topics_technical.xml',
    ],
    'installable': True,
    'application': False,
}
