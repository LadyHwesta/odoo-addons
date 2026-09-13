# -*- coding: utf-8 -*-
{
    'name': 'Club Website Content',
    'version': '19.0.1.0.0',
    'category': 'Website',
    'summary': 'Recreates the club\'s WordPress site content as Odoo website pages',
    'description': """
Club Website Content
======================

Pure content: recreates the static pages and navigation menu of the
club's old WordPress site (sonomacountyradioamateurs.com) as Odoo
``website.page`` records, so the club can run its public site on Odoo's
website builder instead.

Scope, deliberately: this module ports **content**, not functionality.
The WordPress site's transactional pages (membership renewal, event
payment, the auction checkout - all under Store/ and Member Area/) are
not content to import at all - they're application logic, and the right
Odoo equivalent is ``club_membership``'s dues product plus
``website_sale`` and a real payment provider, not a page import. Those
pages are intentionally not recreated here.

Every page's body is plain, unstyled semantic HTML (headings,
paragraphs, lists) - deliberately basic so it renders correctly on
install, then is easy to restyle with the website builder's own
snippets afterward. Nothing here tries to guess at visual design.

A few things noted in each page's content but **not** carried over
automatically, since they're time-bound or files rather than page
content: specific event dates/schedules (Field Day, Winter Field Day,
VE testing sessions - these belong in Odoo's own Events app, re-entered
fresh each time rather than ported as static text), and linked PDFs
(newsletters, insurance policies, code plugs, net scripts) which still
point at the original WordPress site's media URLs until someone
re-uploads them as Odoo attachments.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['website'],
    'data': [
        'data/menus.xml',
        'views/pages_our_club.xml',
        'views/pages_repeaters.xml',
        'views/pages_events.xml',
        'views/pages_resources.xml',
        'views/pages_donate.xml',
    ],
    'installable': True,
    'application': False,
}
