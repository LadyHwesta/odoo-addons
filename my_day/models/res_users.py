# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    my_day_home = fields.Boolean(
        string="Start on My Day", compute='_compute_my_day_home', inverse='_inverse_my_day_home',
        help="Open My Day after logging in.")

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['my_day_home']

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['my_day_home']

    def _my_day_action(self):
        """My Day as Home Action takes it: the generic action model."""
        action = self.env.ref('my_day.action_my_day', raise_if_not_found=False)
        return self.env['ir.actions.actions'].browse(action.id) if action else self.env['ir.actions.actions']

    @api.depends('action_id')
    def _compute_my_day_home(self):
        action = self._my_day_action()
        for user in self:
            user.my_day_home = bool(action) and user.action_id == action

    def _inverse_my_day_home(self):
        action = self._my_day_action()
        for user in self.sudo():
            if user.my_day_home:
                user.action_id = action
            elif action and user.action_id == action:
                user.action_id = False
