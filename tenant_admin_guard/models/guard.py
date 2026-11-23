# -*- coding: utf-8 -*-
"""Who counts as the hosting provider's technical administrator.

Internal code running with sudo is let through: Odoo itself installs a
few modules behind the scenes (a company's localization, say), and no
user can reach sudo from the web client or the API. What's stopped is a
customer administrator doing these things directly.
"""
from odoo import SUPERUSER_ID
from odoo.exceptions import AccessError

GROUP = 'tenant_admin_guard.group_provider_admin'


def is_provider_admin(env):
    if env.su or env.uid == SUPERUSER_ID:
        return True
    provider = env.ref(GROUP, raise_if_not_found=False)
    if not provider:
        return False
    # From the user's groups, not has_group()'s cache: a write that was just
    # refused and rolled back can leave that cache saying yes.
    user = env.user.sudo()
    user.invalidate_recordset(['group_ids'])
    return provider in user.group_ids.all_implied_ids


def check_provider_admin(env, what):
    if not is_provider_admin(env):
        raise AccessError(env._(
            "%(what)s is handled by your hosting provider. Ask them in the "
            "customer portal or by email.", what=what))
