# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    stripe_connect_bridge_url = fields.Char(
        related='company_id.stripe_connect_bridge_url', readonly=False)
    stripe_connect_bridge_token = fields.Char(
        related='company_id.stripe_connect_bridge_token', readonly=False)
    stripe_connect_account_id = fields.Char(
        related='company_id.stripe_connect_account_id', readonly=False)

    def action_stripe_connect_onboarding(self):
        """A fresh Stripe setup link from the bridge (links work once and
        expire after a few minutes, so one is never saved)."""
        self.ensure_one()
        self.execute()  # keep any bridge settings just typed in
        url = self.company_id._get_stripe_connect_bridge_client().create_onboarding_link()
        return {'type': 'ir.actions.act_url', 'url': url, 'target': 'new'}
