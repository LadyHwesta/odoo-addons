# -*- coding: utf-8 -*-
{
    "name": "eLearning: Membership Management",
    "version": "19.0.1.1.0",
    "category": "Website/eLearning",
    "summary": "eLearning course: dues, evacuation zones, and club reporting",
    "description": """
eLearning: Membership Management
==================================

A short, self-contained eLearning course (Odoo's *eLearning* app) for
whoever runs the club's membership side - the Annual Club Dues product
and its yearly proration roll-forward, the Club app's daily rhythm,
evacuation zones, and the Member Roster / Event Statistics / Volunteer
Participation reports. Install this module and the course appears in
eLearning already built - nothing to author by hand.

Only depends on ``club_membership``.
""",
    "author": "Tiesa",
    "license": "LGPL-3",
    "website": "https://github.com/LadyHwesta/odoo-addons",
    "depends": ["website_slides", "club_elearning_theme", "club_membership"],
    "data": [
        "data/slide_channel_data.xml",
    ],
    "application": False,
}
