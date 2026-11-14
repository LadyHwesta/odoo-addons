# -*- coding: utf-8 -*-
{
    "name": "eLearning: Public Meetings",
    "version": "19.0.1.0.0",
    "category": "Website/eLearning",
    "summary": "eLearning course: running a meeting the public can watch",
    "description": """
eLearning: Public Meetings
==========================

A short course for whoever runs public meetings: making a meeting public,
sharing its Watch Link, speaking, what viewers see, and who watched.

Installs itself wherever Public Meetings and the eLearning app are both
installed.
""",
    "author": "Meskis Works",
    "license": "LGPL-3",
    "website": "https://meskis.net",
    "depends": ["website_slides", "calendar_public_meeting"],
    "data": ["data/slide_channel_data.xml"],
    "assets": {
        "web.assets_frontend": [
            "calendar_public_meeting_elearning/static/src/scss/course_content.scss",
        ],
    },
    "auto_install": True,
    "application": False,
}
