# -*- coding: utf-8 -*-
{
    'name': 'Online Booking and Video Appointments',
    'version': '19.0.1.0.0',
    'category': 'Productivity/Calendar',
    'summary': 'A public Book an Appointment page, and video links on booked appointments',
    'description': """
Online Booking and Video Appointments
=====================================

Adds two things to OCA's **Resource Booking** app:

- **Book an appointment online**: tick *Bookable Online* on a booking type and
  it's listed at ``/book``. A new customer enters their name and email, then
  picks a free time from the same page OCA's portal uses. No invitation or
  account needed.
- **Video appointments**: tick *Video Appointment* on a booking type and each
  booked appointment gets its own video link in its invitation: Odoo's video
  call, or Premium telehealth video when the organizer has it.

Each bookable type names an **Organizer**: whose calendar the appointment goes
on, and whose video tier applies.
""",
    'author': 'Meskis Works',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'license': 'AGPL-3',
    'depends': ['resource_booking', 'website'],
    'data': [
        'views/resource_booking_type_views.xml',
        'views/templates.xml',
    ],
    'installable': True,
}
