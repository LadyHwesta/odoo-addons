# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    activitypub_enabled = fields.Boolean(
        string='Enable Fediverse federation',
        config_parameter='activitypub.enabled',
        help='Master switch. While off, the WebFinger, NodeInfo and actor '
             'endpoints all return 404 and nothing is delivered to remote '
             'servers.')
