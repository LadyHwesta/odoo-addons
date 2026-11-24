# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

from .stripe_connect_bridge_client import StripeConnectBridgeClient


class ResCompany(models.Model):
    _inherit = 'res.company'

    stripe_connect_bridge_url = fields.Char(
        string="Meskis Bridge URL", groups="base.group_system",
        help="The reseller's own Odoo base URL - given to you during "
             "setup, e.g. https://meskis.net.")
    stripe_connect_bridge_token = fields.Char(
        string="Meskis Bridge Token", groups="base.group_system",
        help="The bearer token given to you during setup, scoped to "
             "this instance's own Stripe Connect account only - never "
             "the reseller's own Stripe secret key.")
    stripe_connect_account_id = fields.Char(
        string="Stripe Account ID", groups="base.group_system",
        help="Your own Stripe Connect account id (acct_...), also "
             "given to you during setup.")

    stripe_connect_fee_percent = fields.Float(
        string="Meskis Fee (%)", readonly=True, groups="base.group_system",
        help="Meskis' fee on each payment, as the bridge reported it. Refreshed daily; used "
             "when a donor covers the fees.")

    def _stripe_connect_refresh_fee(self):
        """Ask the bridge for the current fee. Quiet on failure: the last known
        value stays."""
        for company in self.filtered(
                lambda c: c.stripe_connect_bridge_url and c.stripe_connect_bridge_token):
            try:
                config = company._get_stripe_connect_bridge_client().checkout_config()
            except Exception:  # bridge down: keep the last value
                continue
            company.stripe_connect_fee_percent = config.get('application_fee_percent') or 0.0

    @api.model
    def _cron_stripe_connect_refresh_fee(self):
        self.sudo().search([])._stripe_connect_refresh_fee()

    def _get_stripe_connect_bridge_client(self):
        self.ensure_one()
        if not self.stripe_connect_bridge_url or not self.stripe_connect_bridge_token:
            raise UserError(
                "Meskis' Stripe Connect bridge isn't configured yet - "
                "Settings > General Settings needs the Bridge URL and "
                "Bridge Token from your setup instructions.")
        return StripeConnectBridgeClient(
            self.stripe_connect_bridge_url, self.stripe_connect_bridge_token)
