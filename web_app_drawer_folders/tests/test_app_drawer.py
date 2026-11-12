# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAppDrawer(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Menu = cls.env['ir.ui.menu']
        # Odoo hides menus that open nothing, so each test app opens a list.
        cls.action = 'ir.actions.act_window,%d' % cls.env.ref('base.action_res_users').id
        cls.alpha, cls.beta, cls.gamma, cls.delta = (
            Menu.create({'name': name, 'sequence': seq, 'action': cls.action})
            for name, seq in (('Alpha', 901), ('Beta', 902), ('Gamma', 903), ('Delta', 904)))
        cls.env['app.drawer.entry'].action_open_settings()
        cls.Entry = cls.env['app.drawer.entry']

    def _place(self, menu, sequence, folder=False):
        self.Entry.search([('menu_id', '=', menu.id)]).write(
            {'sequence': sequence, 'folder_id': folder.id if folder else False})

    def _web_order(self):
        menus = self.env['ir.ui.menu'].load_web_menus(False)
        mine = {self.alpha.id, self.beta.id, self.gamma.id, self.delta.id}
        return [m for m in menus['root']['children'] if m in mine], menus

    def test_every_app_gets_a_place_once(self):
        roots = self.env['ir.ui.menu'].search([('parent_id', '=', False)])
        self.assertEqual(self.Entry.search_count([]), len(roots))
        self.Entry.action_open_settings()
        self.assertEqual(self.Entry.search_count([]), len(roots), "no duplicates on reopening")

    def test_your_order_and_folders(self):
        money = self.env['app.drawer.folder'].create({'name': 'Money', 'sequence': 1})
        phones = self.env['app.drawer.folder'].create({'name': 'Phones', 'sequence': 2})
        self._place(self.delta, 1)
        self._place(self.alpha, 2, phones)
        self._place(self.gamma, 3, money)
        self._place(self.beta, 4, money)

        order, menus = self._web_order()
        self.assertEqual(order, [self.delta.id, self.gamma.id, self.beta.id, self.alpha.id],
                         "outside folders first, then Money, then Phones")
        self.assertFalse(menus[self.delta.id]['drawerFolder'])
        self.assertEqual(menus[self.gamma.id]['drawerFolder'], 'Money')
        self.assertTrue(menus[self.gamma.id]['drawerFolderStart'])
        self.assertFalse(menus[self.beta.id]['drawerFolderStart'])
        self.assertTrue(menus[self.alpha.id]['drawerFolderStart'])

        # Same order for the website pages' dropdown.
        root = self.env['ir.ui.menu'].load_menus_root()
        names = [m['name'] for m in root['children'] if m['name'] in ('Alpha', 'Beta', 'Gamma', 'Delta')]
        self.assertEqual(names, ['Delta', 'Gamma', 'Beta', 'Alpha'])
        gamma = next(m for m in root['children'] if m['name'] == 'Gamma')
        self.assertEqual((gamma['drawer_folder'], gamma['drawer_folder_start']), ('Money', True))

    def test_changes_show_without_waiting_for_the_cache(self):
        self.env['ir.ui.menu'].load_menus_root()
        self._place(self.beta, 1)
        self._place(self.alpha, 2)
        root = self.env['ir.ui.menu'].load_menus_root()
        names = [m['name'] for m in root['children'] if m['name'] in ('Alpha', 'Beta')]
        self.assertEqual(names, ['Beta', 'Alpha'])

    def test_upgrades_resetting_menu_sequences_change_nothing(self):
        self._place(self.gamma, 1)
        self._place(self.alpha, 2)
        before, _menus = self._web_order()
        (self.alpha | self.gamma).write({'sequence': 1})  # what an upgrade does
        self.env.registry.clear_cache()
        after, _menus = self._web_order()
        self.assertEqual(before, after)

    def test_new_apps_go_after_the_placed_ones(self):
        newcomer = self.env['ir.ui.menu'].create({'name': 'Newcomer', 'sequence': 0, 'action': self.action})
        self.env.registry.clear_cache()
        order = self.env['ir.ui.menu'].load_web_menus(False)['root']['children']
        self.assertGreater(order.index(newcomer.id), order.index(self.delta.id))
