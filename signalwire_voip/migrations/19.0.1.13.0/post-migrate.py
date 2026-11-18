# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Show the Customers section only where this database resells."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['signalwire.subproject']._signalwire_sync_reseller_group()
