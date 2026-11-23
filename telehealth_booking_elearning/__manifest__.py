# -*- coding: utf-8 -*-
{
    "name": "eLearning: Telehealth Video Visits",
    "version": "19.0.1.0.0",
    "category": "Website/eLearning",
    "summary": "eLearning course: booking and running telehealth video visits, Basic and Premium",
    "description": """
eLearning: Telehealth Video Visits
==================================

A short course for providers and front-desk staff: the two kinds of video
(Basic, Odoo's built-in calls, and Premium), booking a visit and sending the
patient their link, what the patient sees, and health information.

Installs itself wherever Telehealth Booking and the eLearning app are both
installed.
""",
    "author": "Meskis Works",
    "license": "LGPL-3",
    "website": "https://meskis.net",
    "depends": ["website_slides", "telehealth_booking"],
    "data": ["data/slide_channel_data.xml"],
    "assets": {
        "web.assets_frontend": [
            "telehealth_booking_elearning/static/src/scss/course_content.scss",
        ],
    },
    "auto_install": True,
    "application": False,
}
