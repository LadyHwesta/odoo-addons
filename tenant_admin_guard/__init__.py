# -*- coding: utf-8 -*-
from . import models


def post_init_hook(env):
    """The built-in admin becomes the technical administrator, once, at
    install. Not in data: an upgrade would hand the role back to it on a
    database where it has since been given to a different user."""
    admin = env.ref('base.user_admin', raise_if_not_found=False)
    if admin:
        admin.group_ids = [(4, env.ref('tenant_admin_guard.group_provider_admin').id)]
