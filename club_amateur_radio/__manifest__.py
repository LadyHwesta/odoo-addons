# -*- coding: utf-8 -*-
{
    'name': 'Amateur Radio Club - Member Profiles',
    'version': '19.0.1.0.0',
    'category': 'Association',
    'summary': 'Call sign, FCC licence and ARRL fields on club members, with '
               'call-sign autofill from the FCC ULS (via callook.info)',
    'description': """
Amateur Radio Club - Member Profiles
====================================

Adds an **Amateur Radio** section to every contact:

* Call sign, FCC Registration Number (FRN), operator class, licence grant
  and **expiry** dates, Maidenhead grid square, licence type (individual /
  club / ...), and for a club station licence its trustee.
* An **ARRL member** flag.

**Look up call sign** on the contact form fills all of the above - and the
name and mailing address when they're still blank - straight from the FCC
Universal Licensing System, using the free `callook.info` JSON API (US
amateur licences; call-sign data is public record). No API key.

A nightly cron re-checks every member's licence, refreshes the expiry date,
and raises a To-Do activity for licences expiring within a configurable
window (default 60 days). The lookup can be turned off entirely in
Settings.

Only `requests` (bundled with Odoo) is required.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['contacts', 'mail'],
    'data': [
        'data/ir_cron.xml',
        'views/res_partner_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
}
