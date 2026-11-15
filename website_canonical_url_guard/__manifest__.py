# -*- coding: utf-8 -*-
{
    'name': 'Canonical URL Guard',
    'version': '19.0.1.0.0',
    'category': 'Website/Website',
    'summary': "Bots probing odd addresses get a plain 404, not a server error in the log",
    'description': """
Website: Canonical URL Guard
============================

Odoo 19 builds each page's canonical link with a strict URL join that
refuses paths with dot segments or a leading double slash. Bots probe
exactly those addresses (``//wp-login.php``, ``/%2e%2e/...``), so the
"page not found" page itself failed to render: the visitor got a server
error and the log an ERROR ("Couldn't render a template for http status
404", ValueError from ``odoo.tools.urls.urljoin``), which monitoring then
alerts on.

When the canonical link can't be built safely, this uses the website's
home page instead, so the 404 page renders normally.
""",
    'author': 'Meskis Works',
    'website': 'https://meskis.net',
    'license': 'LGPL-3',
    'support': 'sales@meskis.net',
    'images': ['static/description/banner.png'],
    'depends': ['website'],
    'installable': True,
    'auto_install': True,
}
