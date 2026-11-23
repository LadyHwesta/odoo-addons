# -*- coding: utf-8 -*-
from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestWebsiteAppsDropdown(HttpCase):

    def test_staff_see_folder_headings_on_website_pages(self):
        folder = self.env['app.drawer.folder'].create({'name': 'Bear Things'})
        self.env['app.drawer.entry'].action_open_settings()
        self.env['app.drawer.entry'].search([], limit=2).write({'folder_id': folder.id})
        self.authenticate('admin', 'admin')
        page = self.url_open('/').text
        self.assertIn('o_frontend_to_backend_apps_menu', page)
        self.assertIn('<h6 class="dropdown-header">Bear Things</h6>', page)
        self.assertEqual(page.count('Bear Things'), 1, "one heading for one folder")
