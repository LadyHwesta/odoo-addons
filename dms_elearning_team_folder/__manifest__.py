# -*- coding: utf-8 -*-
{
    "name": "eLearning: Documents, Team Folders, and ONLYOFFICE",
    "version": "19.0.1.1.1",
    "category": "Website/eLearning",
    "summary": "eLearning course: where documents live, connecting ONLYOFFICE, and running team folders",
    "description": """
eLearning: Documents, Team Folders, and ONLYOFFICE
===================================================

A self-contained eLearning course on choosing where documents should live,
connecting ONLYOFFICE, running team folders, and setting them up for common
situations. Install this module and the course appears in eLearning already built.
""",
    "author": "Tiesa",
    "license": "LGPL-3",
    "website": "https://github.com/LadyHwesta/odoo-addons",
    "depends": [
        "website_slides", "club_elearning_theme",
        "dms_team_folder", "dms_onlyoffice",
    ],
    "data": [
        "data/slide_channel_data.xml",
    ],
    "application": False,
}
