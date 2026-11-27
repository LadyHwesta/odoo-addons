# -*- coding: utf-8 -*-
from odoo import api, fields, models

from ..models.support_request import server_setting


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    support_provider_name = fields.Char(
        string="Support provider",
        help="Who escalated requests go to, as people here see it (e.g. your Odoo partner's name).")
    support_provider_email = fields.Char(
        string="Provider's support email",
        help="Escalated requests are emailed here. Leave empty to keep support requests in-house only.")
    support_provider_note = fields.Text(
        string="Note before escalating",
        help="Shown to the coordinator before they send a request, e.g. how help outside a support "
             "plan is billed.")
    support_provider_from_server = fields.Boolean(compute='_compute_support_provider_from_server')

    PARAMS = ('name', 'email', 'note')

    @api.model
    def get_values(self):
        res = super().get_values()
        ICP = self.env['ir.config_parameter'].sudo()
        for key in self.PARAMS:
            res[f'support_provider_{key}'] = (ICP.get_param(f'support_request_escalation.{key}')
                                              or server_setting(key))
        return res

    def set_values(self):
        super().set_values()
        ICP = self.env['ir.config_parameter'].sudo()
        for key in self.PARAMS:
            value = (self[f'support_provider_{key}'] or '').strip()
            # Same as the server's default: don't pin it, so the server can change it.
            if value == server_setting(key):
                value = False
            ICP.set_param(f'support_request_escalation.{key}', value)

    def _compute_support_provider_from_server(self):
        self.support_provider_from_server = bool(server_setting('email'))
