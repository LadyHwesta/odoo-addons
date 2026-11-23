# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class AppDrawerFolder(models.Model):
    """A named group of apps in the app drawer (e.g. "Money", "Phones")."""
    _name = 'app.drawer.folder'
    _description = 'App Drawer Folder'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    entry_ids = fields.One2many('app.drawer.entry', 'folder_id', string="Apps")

    @api.model_create_multi
    def create(self, vals_list):
        self.env.registry.clear_cache()
        return super().create(vals_list)

    def write(self, vals):
        self.env.registry.clear_cache()
        return super().write(vals)

    def unlink(self):
        self.env.registry.clear_cache()
        return super().unlink()


class AppDrawerEntry(models.Model):
    """Where one app sits in the drawer. Kept apart from the menu itself:
    a menu's own sequence is reset by every module upgrade, these aren't."""
    _name = 'app.drawer.entry'
    _description = 'App Drawer Place'
    _order = 'sequence, id'

    menu_id = fields.Many2one(
        'ir.ui.menu', string="App", required=True, ondelete='cascade',
        domain="[('parent_id', '=', False)]")
    sequence = fields.Integer(default=100)
    folder_id = fields.Many2one(
        'app.drawer.folder', string="Folder", ondelete='set null',
        help="Leave empty to keep the app at the top, outside any folder.")
    web_icon = fields.Char(related='menu_id.web_icon')

    _menu_unique = models.Constraint('UNIQUE(menu_id)', "Each app has one place in the drawer.")

    @api.model_create_multi
    def create(self, vals_list):
        self.env.registry.clear_cache()
        return super().create(vals_list)

    def write(self, vals):
        self.env.registry.clear_cache()
        return super().write(vals)

    def unlink(self):
        self.env.registry.clear_cache()
        return super().unlink()

    @api.model
    def _sync_apps(self):
        """One place per app, so the settings list shows every app. New apps
        go at the end, in the order Odoo had them."""
        Menu = self.env['ir.ui.menu'].sudo()
        roots = Menu.search([('parent_id', '=', False)])
        known = self.search([]).menu_id
        last = max(self.search([]).mapped('sequence') or [0])
        new = [{'menu_id': menu.id, 'sequence': last + 10 * (i + 1)}
               for i, menu in enumerate((roots - known).sorted(lambda m: (m.sequence, m.id)))]
        if new:
            self.create(new)

    @api.model
    def action_open_settings(self):
        self._sync_apps()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'web_app_drawer_folders.action_app_drawer_entry')
        return action

    @api.model
    def _drawer_layout(self):
        """{menu_id: (sort_key, folder_name or False)} for every app that has a
        place. Apps outside folders come first, then each folder in order."""
        layout = {}
        for entry in self.sudo().search([]):
            folder = entry.folder_id
            key = (1, folder.sequence, folder.id, entry.sequence, entry.id) if folder \
                else (0, 0, 0, entry.sequence, entry.id)
            layout[entry.menu_id.id] = (key, folder.name if folder else False)
        return layout
