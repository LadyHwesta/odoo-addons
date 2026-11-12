# -*- coding: utf-8 -*-
from odoo import api, models, tools


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    def _drawer_order(self, app_ids):
        """app_ids in drawer order, plus {app_id: (folder, starts_folder)}.
        Apps without a place (installed since the settings were last opened)
        follow the placed ones outside folders, in Odoo's own order."""
        layout = self.env['app.drawer.entry']._drawer_layout()
        unplaced = (0, 0, 0, 10 ** 9)
        ordered = sorted(enumerate(app_ids), key=lambda pair: (
            layout[pair[1]][0] if pair[1] in layout else unplaced + (pair[0],)))
        ordered = [app_id for _index, app_id in ordered]
        folders, previous = {}, False
        for app_id in ordered:
            folder = layout.get(app_id, (None, False))[1]
            folders[app_id] = (folder, bool(folder) and folder != previous)
            previous = folder
        return ordered, folders

    @api.model
    @tools.ormcache('self.env.uid', 'self.env.lang')
    def load_menus_root(self):
        # Used by the website pages' apps dropdown.
        result = super().load_menus_root()
        by_id = {menu['id']: menu for menu in result['children']}
        ordered, folders = self._drawer_order(list(by_id))
        result['children'] = [by_id[app_id] for app_id in ordered]
        for app_id, (folder, starts) in folders.items():
            by_id[app_id]['drawer_folder'] = folder
            by_id[app_id]['drawer_folder_start'] = starts
        return result

    @api.model
    def load_web_menus(self, debug):
        # Used by the backend's app drawer (standard dropdown or web_responsive).
        menus = super().load_web_menus(debug)
        root = menus['root']
        ordered, folders = self._drawer_order(list(root['children']))
        root['children'] = ordered
        for app_id, (folder, starts) in folders.items():
            app = menus.get(app_id) or menus.get(str(app_id))
            if app:
                app['drawerFolder'] = folder
                app['drawerFolderStart'] = starts
        return menus
