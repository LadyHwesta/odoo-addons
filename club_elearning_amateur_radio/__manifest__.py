# -*- coding: utf-8 -*-
{
    "name": "eLearning: License & Callsign Tracking",
    "version": "19.0.1.1.0",
    "category": "Website/eLearning",
    "summary": "eLearning course: FCC call-sign lookup and licence expiry tracking",
    "description": """
eLearning: License & Callsign Tracking
========================================

A short, self-contained eLearning course (Odoo's *eLearning* app) for
whoever keeps member licence records current - looking up a call sign
from the FCC (callook.info), what a lookup fills in versus leaves alone,
and the daily expiry-warning sweep and its settings. Install this module
and the course appears in eLearning already built.

Only depends on ``club_amateur_radio``.
""",
    "author": "Tiesa",
    "license": "LGPL-3",
    "website": "https://github.com/LadyHwesta/odoo-addons",
    "depends": ["website_slides", "club_elearning_theme", "club_amateur_radio"],
    "data": [
        "data/slide_channel_data.xml",
    ],
    "application": False,
}
