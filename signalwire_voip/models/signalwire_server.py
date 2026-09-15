# -*- coding: utf-8 -*-
from odoo import _, models, fields
from odoo.exceptions import UserError

from .signalwire_api import SignalWireClient


class SignalWireServer(models.Model):
    """One SignalWire project's connection settings. In practice
    there's a single one of these for the business - it's the parent
    project whose credentials manage every resold customer's
    subproject too (see signalwire.subproject), since a subproject's
    own auth token can't actually be retrieved via the API (confirmed
    live 2026-09-15 - it comes back masked) but isn't needed anyway.
    """
    _name = 'signalwire.server'
    _description = 'SignalWire Project'

    name = fields.Char(required=True, default='SignalWire')
    space = fields.Char(
        string="Space Domain", required=True, groups="base.group_system",
        help='Your SignalWire Space domain, e.g. '
             '"example.signalwire.com" - no "https://" prefix.')
    project_id = fields.Char(
        string="Project ID", required=True, groups="base.group_system",
        help="Settings -> API in your SignalWire dashboard.")
    api_token = fields.Char(
        string="API Token", required=True, groups="base.group_system",
        help="Generated alongside the Project ID. Needs at least the "
             "Voice and Numbers scopes for everything this module "
             "does; Messaging too once signalwire_sms is installed.")
    active = fields.Boolean(default=True)

    def _get_client(self):
        self.ensure_one()
        return SignalWireClient(
            space=self.space, project_id=self.project_id, api_token=self.api_token)

    def action_test_connection(self):
        self.ensure_one()
        client = self._get_client()
        result = client.compat_get(f'Accounts/{self.project_id}.json')
        raise UserError(_(
            "Connected. Project status: %(status)s.",
            status=result.get('status', '?')))

    def search_available_numbers(self, account_sid, country, area_code=None):
        """Numbers available to purchase within the subproject
        `account_sid`, as a list of E.164 strings. Search is free -
        nothing is reserved or charged by looking.

        :param country: ISO country code SignalWire recognizes for
            number search, e.g. "US" or "CA" - not validated here,
            SignalWire's own error surfaces a bad one.
        :param area_code: optional, narrows results (US/CA only).
        """
        self.ensure_one()
        client = self._get_client()
        params = {'AreaCode': area_code} if area_code else {}
        result = client.compat_get(
            f'Accounts/{account_sid}/AvailablePhoneNumbers/{country}/Local.json',
            **params)
        return [n['phone_number'] for n in result.get('available_phone_numbers', [])]
