{
    'name': 'CalDAV Calendar Sync',
    'version': '19.0.2.3.0',
    'category': 'Productivity/Calendar',
    'summary': 'Two-way calendar synchronization with any RFC 4791 CalDAV server',
    'description': """
CalDAV Calendar Sync
=====================

Synchronizes Odoo's Calendar app with any standards-compliant CalDAV server
(Nextcloud, Radicale, Baikal, Fastmail, iCloud, ...), the same way the core
``google_calendar`` / ``microsoft_calendar`` modules sync with their
respective providers.

Each user can add any number of CalDAV calendar accounts (URL + username +
password or app-specific password) from their Preferences - each one syncs
independently. Odoo then:

* Pulls remote changes using RFC 6578 ``sync-collection`` when the server
  supports it, falling back to a ``getctag`` + full report comparison
  otherwise.
* Pushes local ``calendar.event`` creates/updates/deletes back to the server,
  using ``ETag`` preconditions to avoid clobbering concurrent remote edits.
* Runs automatically on a scheduled action, and can also be triggered
  manually from Preferences.

No extra Python packages are required: this module only relies on
``requests``, ``lxml`` and ``vobject``, which are already core Odoo
dependencies.

Recurring events sync in full, including per-occurrence exceptions
(``RECURRENCE-ID`` overrides and ``EXDATE``), not just the master rule.
See README.md for known edge cases and other limitations.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'images': ['static/description/banner.png'],
    'depends': ['calendar', 'mail'],
    'external_dependencies': {
        'python': ['requests', 'lxml', 'vobject'],
    },
    'data': [
        'security/ir.model.access.csv',
        'security/caldav_security.xml',
        'data/ir_cron.xml',
        'views/caldav_account_views.xml',
        'views/res_users_views.xml',
        'views/calendar_event_views.xml',
        'wizard/caldav_calendar_select_views.xml',
    ],
    'installable': True,
    'application': False,
}
