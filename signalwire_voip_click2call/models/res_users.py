# -*- coding: utf-8 -*-
import secrets

from odoo import _, models, fields
from odoo.exceptions import UserError


class ResUsers(models.Model):
    _inherit = 'res.users'

    signalwire_sip_endpoint_id = fields.Char(
        string="SignalWire SIP Endpoint ID", copy=False,
        help="SignalWire's own ID for this user's SIP Endpoint - "
             "needed to release it later. Set automatically by "
             "\"Provision SignalWire Softphone\", not editable by hand.")
    signalwire_server_id = fields.Many2one(
        'signalwire.server', copy=False,
        help="Which project this user's SIP Endpoint (if any) lives on.")

    def action_provision_signalwire_sip(self):
        """One-click softphone setup: creates a real SIP Endpoint at
        SignalWire for this user and wires voip_oca's own
        voip_username/voip_password/voip_pbx_id fields to it -
        confirmed live 2026-09-15 (see signalwire_voip's own tests/
        README) that SIP Endpoint creation works with a plain project
        token, no extra scope needed beyond what's already required.
        """
        self.ensure_one()
        if self.signalwire_sip_endpoint_id:
            raise UserError(_(
                "%(user)s already has a SignalWire softphone provisioned.",
                user=self.name))
        server = self.env['signalwire.server'].search([], limit=1)
        if not server:
            raise UserError(_("No SignalWire project is configured yet."))

        pbx = self.env['voip.pbx'].search([('name', '=', server.name)], limit=1)
        if not pbx:
            pbx = server.action_setup_click2call()

        # A plain user{id} username, not the login - nobody ever needs
        # to see or type this, it just has to be unique and safe for a
        # SIP URI, and Odoo's own user IDs already guarantee that
        # without having to sanitize arbitrary login strings.
        username = f'user{self.id}'
        password = secrets.token_urlsafe(18)
        result = server._get_client().relay_post(
            'endpoints/sip', username=username, password=password)

        self.write({
            'signalwire_sip_endpoint_id': result['id'],
            'signalwire_server_id': server.id,
            'voip_pbx_id': pbx.id,
            'voip_username': result['username'],
            'voip_password': password,
        })

    def action_release_signalwire_sip(self):
        self.ensure_one()
        if not self.signalwire_sip_endpoint_id:
            raise UserError(_(
                "%(user)s has no SignalWire softphone provisioned.", user=self.name))
        self.signalwire_server_id._get_client().relay_delete(
            f'endpoints/sip/{self.signalwire_sip_endpoint_id}')
        self.write({
            'signalwire_sip_endpoint_id': False,
            'signalwire_server_id': False,
            'voip_username': False,
            'voip_password': False,
        })
