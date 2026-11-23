# -*- coding: utf-8 -*-
"""Python written from the web client: server actions and scheduled
actions of type "Execute Code" (scheduled actions are server actions
underneath, and so are automation rules' actions), and computed custom
fields."""
from odoo import api, models

from .guard import check_provider_admin


def _code(env):
    check_provider_admin(env, env._("Writing code in actions or fields"))


class IrActionsServer(models.Model):
    _inherit = 'ir.actions.server'

    # The web client sends a default "code" value for every kind of action,
    # so only actions that end up running code count.
    @api.model_create_multi
    def create(self, vals_list):
        default = self.default_get(['state']).get('state')
        if any(vals.get('state', default) == 'code' for vals in vals_list):
            _code(self.env)
        return super().create(vals_list)

    def write(self, vals):
        if 'state' in vals or 'code' in vals:
            if any(vals.get('state', action.state) == 'code' for action in self):
                _code(self.env)
        return super().write(vals)


class IrModelFields(models.Model):
    _inherit = 'ir.model.fields'

    @api.model_create_multi
    def create(self, vals_list):
        if any(vals.get('compute') for vals in vals_list):
            _code(self.env)
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('compute'):
            _code(self.env)
        return super().write(vals)
