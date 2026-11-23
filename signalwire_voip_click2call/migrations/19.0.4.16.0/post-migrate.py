# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Numbers connected before this version don't send a status callback,
    so a call that ends while ringing stays "in progress" on the panel
    until the cleanup job. Give them one now (failures are only logged)."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['signalwire.phone_number'].search(
        [('inbound_connected', '=', True)])._signalwire_set_status_callback()
