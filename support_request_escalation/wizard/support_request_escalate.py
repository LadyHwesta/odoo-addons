# -*- coding: utf-8 -*-
from odoo import _, api, fields, models

from ..models.support_request import provider_setting


class SupportRequestEscalate(models.TransientModel):
    _name = 'support.request.escalate'
    _description = 'Send a support request to the provider'

    request_id = fields.Many2one('support.request', required=True, ondelete='cascade')
    provider_name = fields.Char(compute='_compute_provider')
    provider_email = fields.Char(compute='_compute_provider')
    provider_note = fields.Text(compute='_compute_provider')
    note = fields.Text(string="Message to support",
                       help="Anything you already tried, or that they should know. The request's details "
                            "and the page it came from are included for you.")

    @api.depends('request_id')
    def _compute_provider(self):
        for wizard in self:
            wizard.provider_name = provider_setting(self.env, 'name') or _("your Odoo provider")
            wizard.provider_email = provider_setting(self.env, 'email')
            wizard.provider_note = provider_setting(self.env, 'note')

    def action_send(self):
        self.ensure_one()
        self.request_id._escalate(self.note or '')
        return {'type': 'ir.actions.act_window_close'}
