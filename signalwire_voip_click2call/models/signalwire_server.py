# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class SignalWireServer(models.Model):
    _inherit = 'signalwire.server'

    sip_domain = fields.Char(
        string="SIP Domain", groups="base.group_system",
        help="The real hostname SIP.js/JsSIP and desk phones register "
             "and dial against - copy it from this SignalWire "
             "project's dashboard, SIP Profile page "
             "(https://<space>.signalwire.com/sip_profile/edit). "
             "**This is NOT just your Space domain with \".sip.\" "
             "inserted** - SignalWire support confirmed (2026-09-20) "
             "that each space's real SIP domain carries an additional "
             "hidden, space-specific suffix (e.g. "
             "\"yourspace-4bfcc2d4e531.sip.signalwire.com\") that "
             "can't be derived from the space name alone.")

    def _get_sip_domain(self):
        """The hostname SIP.js/JsSIP and desk phones actually register
        and dial against for this project - must be configured
        directly from the SIP Profile field above, never derived: an
        earlier version of this method guessed it from the Space
        domain (`{space}.sip.signalwire.com`), which looked plausible
        (it does accept a WebSocket upgrade and challenge a REGISTER
        with a real 401) but was silently wrong - SignalWire support
        confirmed the real domain carries a hidden per-space suffix
        the bare space name doesn't include, which is exactly why
        every real registration attempt against the guessed domain
        failed authentication despite cryptographically correct
        digest credentials.
        """
        self.ensure_one()
        if not self.sip_domain:
            raise UserError(_(
                "This SignalWire project's SIP Domain isn't configured "
                "yet. Copy the real value from "
                "https://%(space)s/sip_profile/edit - it is NOT just "
                "your Space domain with \".sip.\" inserted.",
                space=self.space))
        return self.sip_domain

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
