# -*- coding: utf-8 -*-
"""Keeps the technical administrator's account out of a customer
administrator's reach, and the role out of anyone else's.

The email is guarded too: "Reset password" mails a link to it, so whoever
can change it can take the account.
"""
from odoo import api, models

from .guard import GROUP, is_provider_admin, check_provider_admin

SENSITIVE_USER_FIELDS = {'login', 'password', 'active', 'group_ids', 'role', 'email', 'partner_id'}


def _account(env):
    check_provider_admin(env, env._("Changing the technical administrator's account"))


def _role(env):
    check_provider_admin(env, env._("Giving someone the technical administrator role"))


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _provider_admins(self):
        # From the groups themselves, not has_group()'s per-user cache, which
        # can still hold the answer from before a write in this transaction.
        provider = self.env.ref(GROUP, raise_if_not_found=False)
        if not provider:
            return self.browse()
        self.invalidate_recordset(['group_ids', 'all_group_ids'])
        return self.filtered(lambda u: provider in u.group_ids.all_implied_ids)

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        if not is_provider_admin(self.env) and users._provider_admins():
            _role(self.env)
        return users

    def write(self, vals):
        if is_provider_admin(self.env):
            return super().write(vals)
        if SENSITIVE_USER_FIELDS & set(vals) and self.sudo()._provider_admins():
            _account(self.env)
        before = self.sudo()._provider_admins()
        result = super().write(vals)
        if self.sudo()._provider_admins() - before:
            _role(self.env)
        return result

    def unlink(self):
        if not is_provider_admin(self.env) and self.sudo()._provider_admins():
            _account(self.env)
        return super().unlink()


class ResGroups(models.Model):
    _inherit = 'res.groups'

    def _grants_provider_admin(self):
        provider = self.env.ref(GROUP, raise_if_not_found=False)
        return provider and any(
            g == provider or provider in g.sudo().all_implied_ids for g in self)

    @api.model_create_multi
    def create(self, vals_list):
        groups = super().create(vals_list)
        if not is_provider_admin(self.env) and groups._grants_provider_admin():
            _role(self.env)
        return groups

    def write(self, vals):
        if is_provider_admin(self.env):
            return super().write(vals)
        if self._grants_provider_admin():
            _role(self.env)
        result = super().write(vals)
        if self._grants_provider_admin():
            _role(self.env)
        return result

    def unlink(self):
        if not is_provider_admin(self.env) and self._grants_provider_admin():
            _role(self.env)
        return super().unlink()


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def write(self, vals):
        if 'email' in vals and not is_provider_admin(self.env):
            users = self.sudo().with_context(active_test=False).user_ids
            if users._provider_admins():
                _account(self.env)
        return super().write(vals)
