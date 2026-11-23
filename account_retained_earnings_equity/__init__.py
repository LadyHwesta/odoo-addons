# -*- coding: utf-8 -*-
from . import models


def _post_init_hook(env):
    env['account.account']._retype_retained_earnings()
