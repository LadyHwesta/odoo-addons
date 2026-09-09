# -*- coding: utf-8 -*-
{
    'name': 'Amateur Radio Club',
    'version': '19.0.1.1.0',
    'category': 'Association',
    'summary': 'Club-centric bundle: members with prorated dues and licences, '
               'events with volunteers, a loaner equipment library, and one '
               'member portal',
    'description': """
Amateur Radio Club
==================

The umbrella module. Installing this pulls in the whole club suite and
ties it together:

* **Members** - `membership` + `membership_prorate` (calendar-year dues,
  prorated for mid-year joiners) + `membership_withdrawal` +
  `website_membership` (opt-in public directory).
* **Licences** - `club_amateur_radio` (call sign / FCC licence / ARRL, with
  call-sign autofill).
* **Events** - `event_volunteer` (volunteer roles + sign-up).
* **Equipment** - `club_equipment_loan` (loaner library).

On top of those it adds:

* A single **Club** app menu gathering Members, Events, Volunteers,
  Equipment Loans and the configuration bits in one place.
* An **Annual Dues** membership product, prorate on, dated to the current
  calendar year - with a New Year cron that rolls it to the next year so
  proration keeps working without anyone remembering to.
* A **member portal home** at `/my/club`: dues status, licence class and
  expiry, equipment currently out, and upcoming volunteer commitments -
  plus a card for it on the portal home.

No extra Python packages.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': [
        'membership',
        'membership_prorate',
        'membership_withdrawal',
        'website_membership',
        'club_amateur_radio',
        'event_volunteer',
        'club_equipment_loan',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/product_data.xml',
        'data/ir_cron.xml',
        'views/club_evacuation_zone_views.xml',
        'views/res_partner_views.xml',
        'views/report_club_event_views.xml',
        'views/event_volunteer_report_views.xml',
        'report/member_roster_report.xml',
        'views/club_menus.xml',
        'views/club_portal_templates.xml',
    ],
    'application': True,
    'installable': True,
}
