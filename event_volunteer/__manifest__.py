# -*- coding: utf-8 -*-
{
    'name': 'Event Volunteer Roles',
    'version': '19.0.1.0.0',
    'category': 'Marketing/Events',
    'summary': 'Named volunteer positions with slot quotas on events, and '
               'member self sign-up from the website',
    'description': """
Event Volunteer Roles
=====================

Core Events lets people register to *attend*. This adds the other half a
club needs: signing up to *help run* an event.

* Give an event any number of **volunteer roles** - "Net Control",
  "Setup Crew", "Talk-in Station", "GOTA Coach" - each with how many
  people it needs.
* Members claim a slot from the event's website page; a role that's full
  stops taking sign-ups. They can withdraw again themselves.
* The event form gets a **Volunteers** tab: the roster grouped by role,
  with an at-a-glance filled / needed count, and an over/under-filled
  indicator.
* A confirmation email on sign-up, and a reminder a couple of days before
  the event (both editable templates; the lead time is a setting).

Requires `event` and `website_event`. No extra Python packages.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['event', 'website_event'],
    'data': [
        'security/ir.model.access.csv',
        'security/event_volunteer_security.xml',
        'data/mail_template_data.xml',
        'data/ir_cron.xml',
        'views/event_volunteer_views.xml',
        'views/event_event_views.xml',
        'views/res_config_settings_views.xml',
        'views/event_volunteer_portal_templates.xml',
    ],
    'installable': True,
    'application': False,
}
