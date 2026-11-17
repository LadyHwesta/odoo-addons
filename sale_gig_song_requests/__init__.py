# -*- coding: utf-8 -*-
import secrets

from . import controllers
from . import models


def _post_init_hook(env):
    """Gigs that already exist get their private request link too."""
    for order in env['sale.order'].search([('song_request_token', '=', False)]):
        order.song_request_token = secrets.token_urlsafe(12)
