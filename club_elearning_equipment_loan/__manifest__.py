# -*- coding: utf-8 -*-
{
    "name": "eLearning: Equipment Loans",
    "version": "19.0.1.0.0",
    "category": "Website/eLearning",
    "summary": "eLearning course: the loaner equipment library workflow",
    "description": """
eLearning: Equipment Loans
============================

A short, self-contained eLearning course (Odoo's *eLearning* app) for
whoever runs the club's loaner equipment library - marking gear loanable,
the checkout/check-in workflow and the borrower-acceptance gate, and the
overdue sweep plus the borrower's own portal view. Install this module
and the course appears in eLearning already built.

Only depends on ``club_equipment_loan``.
""",
    "author": "Tiesa",
    "license": "LGPL-3",
    "website": "https://github.com/LadyHwesta/odoo-addons",
    "depends": ["website_slides", "club_equipment_loan"],
    "data": [
        "data/slide_channel_data.xml",
    ],
    "application": False,
}
