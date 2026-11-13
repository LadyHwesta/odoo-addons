# -*- coding: utf-8 -*-
from odoo import models

from .guard import GROUP

# Hidden here rather than by changing the menus' groups: other modules set
# those too (base_install_request, auto-installed, opens Apps to everyone),
# and whichever loads last would win.
PROVIDER_MENUS = ('base.menu_management', 'base.menu_custom')


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    def _visible_menu_ids(self, debug=False):
        # Cached per set of groups, so the provider's own result is separate.
        visible = super()._visible_menu_ids(debug)
        provider = self.env.ref(GROUP, raise_if_not_found=False)
        if self.env.su or not provider or provider.id in self.env.user._get_group_ids():
            return visible
        roots = [self.env.ref(xmlid, raise_if_not_found=False) for xmlid in PROVIDER_MENUS]
        hidden = self.sudo().with_context(active_test=False).search(
            [('id', 'child_of', [m.id for m in roots if m])])
        return visible - set(hidden.ids)
