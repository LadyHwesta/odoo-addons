# -*- coding: utf-8 -*-
from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestAppGridFolders(HttpCase):
    """The full-screen app grid, in a real browser, shows folder headings."""

    def test_grid_shows_folder_headings(self):
        folder = self.env['app.drawer.folder'].create({'name': 'Bear Things'})
        self.env['app.drawer.entry'].action_open_settings()
        self.env['app.drawer.entry'].search([], limit=2).write({'folder_id': folder.id})
        code = """
            (async () => {
                document.querySelector('.o_grid_apps_menu__button').click();
                for (let i = 0; i < 50 && !document.querySelector('.o_app_drawer_folder_row'); i++) {
                    await new Promise((r) => setTimeout(r, 100));
                }
                const row = document.querySelector('.o_app_drawer_folder_row');
                if (!row || !row.textContent.includes('Bear Things')) {
                    throw new Error('no folder heading in the grid');
                }
                if (document.querySelectorAll('.o_app_drawer_folder_row').length !== 1) {
                    throw new Error('one folder, one heading');
                }
                console.log('test successful');
            })().catch((e) => console.error(e.message));
        """
        self.browser_js('/odoo', code, ready="!!document.querySelector('.o_grid_apps_menu__button')",
                        login='admin', timeout=120)
