# -*- coding: utf-8 -*-
{
    "name": "eLearning: Online Booking",
    "version": "19.0.1.0.0",
    "category": "Website/eLearning",
    "summary": "eLearning course: letting customers book appointments, including by video",
    "description": """
eLearning: Online Booking
=========================

A short course on the Resource Bookings app with online booking: who can be
booked and when, booking types, the public Book an Appointment page, video
appointments, inviting someone to pick a time, and managing bookings.

Installs itself wherever Online Booking and the eLearning app are both
installed.
""",
    "author": "Meskis Works",
    "license": "AGPL-3",
    "website": "https://github.com/LadyHwesta/odoo-addons",
    "depends": ["website_slides", "resource_booking_online"],
    "data": ["data/slide_channel_data.xml"],
    "assets": {
        "web.assets_frontend": [
            "resource_booking_online_elearning/static/src/scss/course_content.scss",
        ],
    },
    "auto_install": True,
    "application": False,
}
