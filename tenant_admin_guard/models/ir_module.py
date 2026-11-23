# -*- coding: utf-8 -*-
from odoo import models

from .guard import check_provider_admin


def _apps(env):
    check_provider_admin(env, env._("Installing, removing or upgrading apps"))


class IrModuleModule(models.Model):
    _inherit = 'ir.module.module'

    def button_install(self):
        _apps(self.env)
        return super().button_install()

    def button_immediate_install(self):
        _apps(self.env)
        return super().button_immediate_install()

    def button_reset_state(self):
        _apps(self.env)
        return super().button_reset_state()

    def module_uninstall(self):
        _apps(self.env)
        return super().module_uninstall()

    def button_immediate_uninstall(self):
        _apps(self.env)
        return super().button_immediate_uninstall()

    def button_uninstall(self):
        _apps(self.env)
        return super().button_uninstall()

    def button_uninstall_wizard(self):
        _apps(self.env)
        return super().button_uninstall_wizard()

    def button_immediate_upgrade(self):
        _apps(self.env)
        return super().button_immediate_upgrade()

    def button_upgrade(self):
        _apps(self.env)
        return super().button_upgrade()

    def update_list(self):
        _apps(self.env)
        return super().update_list()

    def write(self, vals):
        # The state is what the upgrade wizard acts on.
        if 'state' in vals:
            _apps(self.env)
        return super().write(vals)


class BaseModuleUpgrade(models.TransientModel):
    _inherit = 'base.module.upgrade'

    def upgrade_module(self):
        _apps(self.env)
        return super().upgrade_module()


class BaseModuleUpdate(models.TransientModel):
    _inherit = 'base.module.update'

    def update_module(self):
        _apps(self.env)
        return super().update_module()


class BaseModuleUninstall(models.TransientModel):
    _inherit = 'base.module.uninstall'

    def action_uninstall(self):
        _apps(self.env)
        return super().action_uninstall()
