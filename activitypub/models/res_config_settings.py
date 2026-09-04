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
    activitypub_replies_to_chatter = fields.Boolean(
        string='Post federated replies to chatter',
        config_parameter='activitypub.replies_to_chatter',
        default=True,
        help='When someone on the Fediverse replies to a federated record '
             '(a blog post, an event), post their reply to that record\'s '
             'chatter as a comment.')
    activitypub_ssrf_allow_hosts = fields.Char(
        string='SSRF allowlist',
        config_parameter='activitypub.ssrf_allow_hosts',
        help='Comma-separated hostnames exempt from the SSRF guard on '
             'outbound federation requests. Leave empty in production; set it '
             'only for a self-hosted test rig where the peer server is on a '
             'private network.')
