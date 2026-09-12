# -*- coding: utf-8 -*-
{
    "name": "eLearning: Shared Course Styling",
    "version": "19.0.1.0.0",
    "category": "Website/eLearning",
    "summary": "Shared visual styling for this suite's eLearning course lessons",
    "description": """
eLearning: Shared Course Styling
==================================

A pure-assets module - no models, no data - providing the callout boxes,
numbered step lists, state badges, and diagram styling used by every
``club_elearning_*`` course in this repo, so the CSS lives in one place
instead of being duplicated across three modules. Not meant to be
installed on its own for any visible effect; the other eLearning packs
depend on it.
""",
    "author": "Tiesa",
    "license": "LGPL-3",
    "website": "https://github.com/LadyHwesta/odoo-addons",
    "depends": ["website_slides"],
    "data": [],
    "assets": {
        "web.assets_frontend": [
            "club_elearning_theme/static/src/scss/course_content.scss",
        ],
    },
    "application": False,
}
