{
    'name': 'IMAP Authentication',
    'version': '19.0.1.0.0',
    'category': 'Extra Tools',
    'summary': 'Authenticate existing Odoo users against an IMAP mail server',
    'description': """
IMAP Authentication
=====================

Lets existing Odoo users log in with their mailbox password, by
authenticating against an IMAP server (``LOGIN``) - the same mail server
password they already use, instead of (or as a fallback to) a separate
Odoo password.

Mirrors the structure of core's own ``auth_ldap`` module: a user's local
Odoo password is checked first, and only on failure does Odoo fall back to
attempting an IMAP login with the submitted credentials. This means an
admin account (or anyone who still has a local password set) is never at
risk of being locked out just because the mail server is unreachable.

Unlike ``auth_ldap``, this module does **not** auto-provision new Odoo
users: IMAP only authenticates users who already have an Odoo account
(matched by login). To move an existing user onto IMAP-only
authentication, use the "Convert to IMAP Authentication" action on their
user record(s) - it clears their local Odoo password, so every future
login for them falls through to the IMAP check.

No extra Python packages required: uses ``imaplib`` from the Python
standard library.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'images': ['static/description/banner.png'],
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_company_imap_views.xml',
        'views/res_users_views.xml',
    ],
    'installable': True,
    'application': False,
}
