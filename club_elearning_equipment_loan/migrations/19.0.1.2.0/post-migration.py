# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api
from odoo.tools import convert_file


def migrate(cr, version):
    """The course data is noupdate, so a normal upgrade won't touch lessons that
    already exist. Reload it so corrections and screenshots reach installed
    courses. This replaces any hand edits made to these lessons.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    convert_file(
        env, "club_elearning_equipment_loan", "data/slide_channel_data.xml", {},
        mode="init", noupdate=True)
