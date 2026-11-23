# -*- coding: utf-8 -*-
{
    'name': 'Missing Argument Guard',
    'version': '19.0.1.0.0',
    'category': 'Hidden/Tools',
    'summary': "Requests missing a page's required values get a plain 404, not a server error",
    'description': """
Missing Argument Guard
======================

Odoo passes the values in a request's address and form straight to the
page's code. When a page needs a value the request doesn't carry
(``/scoped_app`` without ``app_id``, for example), Odoo doesn't check:
the code crashes with a TypeError, the visitor gets a server error and
the log an ERROR with a full traceback. Real visitors never do this,
because Odoo always builds those links itself; scanners do it all day.

This checks every request before the page runs. If a value the page
requires is missing, the answer is a plain 404 (or a JSON-RPC 404
error), which isn't logged as an error. Pages that get everything they
need are untouched.
""",
    'author': 'Meskis Works',
    'website': 'https://meskis.net',
    'license': 'LGPL-3',
    'support': 'sales@meskis.net',
    'images': ['static/description/banner.png'],
    'depends': ['web'],
    'installable': True,
    'auto_install': True,
}
