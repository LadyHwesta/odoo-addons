# -*- coding: utf-8 -*-
from odoo import models

from .guard import is_provider_admin, check_provider_admin


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    def execute(self):
        """Settings that would install or remove an app are refused before
        anything is saved, so the rest of the page isn't half-applied."""
        self.ensure_one()
        if not is_provider_admin(self.env):
            modules = self.with_context(active_test=False)._get_classified_fields()['module']
            changing = modules.filtered(
                lambda m: bool(self[f'module_{m.name}']) != (m.state in ('installed', 'to upgrade')))
            if changing:
                check_provider_admin(self.env, self.env._(
                    "Turning on or off a setting that adds or removes an app (%(apps)s)",
                    apps=", ".join(changing.mapped('shortdesc'))))
        return super().execute()
