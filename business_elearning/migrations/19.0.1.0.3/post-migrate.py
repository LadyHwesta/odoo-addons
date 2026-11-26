# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api
from odoo.tools import convert_file


def migrate(cr, version):
    """The course data is noupdate, so a normal upgrade won't touch lessons that
    already exist. Reload it so the My Day lesson explains the new sliders
    button and Preferences tab (my_day 19.0.1.2.0). This replaces any hand
    edits made to these lessons. Loads after website_slides_publication_digest
    (through accounting_elearning), so the reload doesn't email anyone.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    convert_file(
        env, "business_elearning", "data/slide_channel_data.xml", {},
        mode="init", noupdate=True)
