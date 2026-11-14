# -*- coding: utf-8 -*-
{
    "name": "eLearning: Video Meetings",
    "version": "19.0.1.0.0",
    "category": "Website/eLearning",
    "summary": "eLearning course: meetings with video calls, documents, and the call controls",
    "description": """
eLearning: Video Meetings
=========================

A short course for anyone running or joining meetings with Odoo's built-in
video calls: adding video to a meeting, inviting people outside the
organization, the meeting's documents (and keeping some private), the call
controls, Gallery and Speaker view, and opening documents during a call.

Installs itself wherever the meeting documents and call view add-ons and
the eLearning app are all installed.
""",
    "author": "Meskis Works",
    "license": "LGPL-3",
    "website": "https://meskis.net",
    "depends": ["website_slides", "calendar_event_documents", "discuss_call_layout"],
    "data": ["data/slide_channel_data.xml"],
    "assets": {
        "web.assets_frontend": [
            "elearning_video_meetings/static/src/scss/course_content.scss",
        ],
    },
    "auto_install": True,
    "application": False,
}
