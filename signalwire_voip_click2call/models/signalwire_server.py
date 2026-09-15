# -*- coding: utf-8 -*-
from odoo import models


class SignalWireServer(models.Model):
    _inherit = 'signalwire.server'

    def _get_sip_domain(self):
        """The hostname SIP.js/JsSIP actually registers and dials
        against for this project. **Confirmed live 2026-09-15**: this
        is NOT the bare Space domain (`self.space`) - that one serves
        the web dashboard, and refuses/redirects any WebSocket upgrade
        attempt to the login page. The real SIP-over-WebSocket
        endpoint lives at a distinct host with ``.sip.`` inserted -
        verified by a raw WebSocket handshake against it, which came
        back ``101 Switching Protocols`` / ``Server: SignalWire Proxy``
        with the ``sip`` subprotocol accepted.
        """
        self.ensure_one()
        space_name = self.space.split('.signalwire.com')[0]
        return f'{space_name}.sip.signalwire.com'

    def action_setup_click2call(self):
        """Create (or update) the one voip_oca ``voip.pbx`` record this
        project needs - every user's softphone shares it, only the
        per-user SIP Endpoint credentials differ (see res.users).
        """
        self.ensure_one()
        sip_domain = self._get_sip_domain()
        vals = {
            'name': self.name,
            'domain': sip_domain,
            'ws_server': f'wss://{sip_domain}',
            'mode': 'prod',
        }
        pbx = self.env['voip.pbx'].search([('name', '=', self.name)], limit=1)
        if pbx:
            pbx.write(vals)
        else:
            pbx = self.env['voip.pbx'].create(vals)
        return pbx
