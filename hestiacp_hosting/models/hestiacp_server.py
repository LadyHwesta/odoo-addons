# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

from .hestiacp_api import HestiaCPAPIError, HestiaCPClient


class HestiaCPServer(models.Model):
    """A HestiaCP server this Odoo instance can provision accounts on.

    Kept as its own model (rather than a single set of config
    parameters) from day one so adding a second server later - to
    spread load, or offer a different plan tier on different hardware
    - is just a new record, not a refactor.
    """
    _name = 'hestiacp.server'
    _description = 'HestiaCP Server'

    name = fields.Char(required=True, help="Internal label, e.g. \"US-East 1\".")
    hostname = fields.Char(
        required=True,
        help="e.g. https://host.example.com:8083 - include the scheme and API port.")
    access_key = fields.Char(
        required=True, groups="base.group_system",
        help="Public half of a HestiaCP Access Key (Server > Access Keys). "
             "Grant it the \"billing\" permission category - the only one of "
             "HestiaCP's 6 built-in categories that covers account "
             "add/suspend/unsuspend/delete/package/password (verified "
             "2026-09-14; see README's HestiaCP API notes).")
    secret_key = fields.Char(
        required=True, groups="base.group_system")
    active = fields.Boolean(default=True)
    account_ids = fields.One2many('hestiacp.account', 'server_id', string="Accounts")
    account_count = fields.Integer(compute='_compute_account_count')

    @api.depends('account_ids')
    def _compute_account_count(self):
        for server in self:
            server.account_count = len(server.account_ids)

    def _get_client(self):
        self.ensure_one()
        return HestiaCPClient(self.hostname, self.access_key, self.secret_key)

    def action_view_accounts(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._("Accounts"),
            'res_model': 'hestiacp.account',
            'view_mode': 'list,form',
            'domain': [('server_id', '=', self.id)],
            'context': {'default_server_id': self.id},
        }

    def action_test_connection(self):
        self.ensure_one()
        client = self._get_client()
        try:
            # v-list-sys-info isn't reachable through any of HestiaCP's
            # built-in Access Key permission categories (verified
            # 2026-09-14) - v-list-users is, under "billing", and doubles
            # as a real check that account-management commands work.
            client.call('v-list-users', 'json')
        except HestiaCPAPIError as exc:
            raise UserError(
                self.env._("Connection failed: %(error)s", error=str(exc))
            ) from exc
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': self.env._("Connection successful"),
                'message': self.env._("%(name)s responded to v-list-users.", name=self.name),
                'type': 'success',
            },
        }
