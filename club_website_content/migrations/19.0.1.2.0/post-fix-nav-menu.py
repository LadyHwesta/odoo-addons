# -*- coding: utf-8 -*-
"""Fix for an install that predates 19.0.1.2.0: rebuild the nav menu and
re-set the homepage, both correctly scoped to one real website, replacing
whatever the old data/menus.xml + data/website_config.xml produced. See
hooks.py's create_nav_menu() docstring (MENU_BUG) for the full story.
"""
from odoo import api, SUPERUSER_ID
from odoo.addons.club_website_content.hooks import setup_website_content


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    setup_website_content(env)
