# -*- coding: utf-8 -*-
import base64
import hashlib
import hmac
import time

from odoo import _, fields, models
from odoo.exceptions import UserError


class SignalWireServer(models.Model):
    _inherit = 'signalwire.server'

    turn_host = fields.Char(
        string="TURN Server", groups="base.group_system",
        help="host:port of a TURN relay for call audio, e.g. "
             "\"turn.example.com:3478\". Without one, outgoing calls can "
             "fail with \"MEDIA_TIMEOUT\" on some networks. Leave blank "
             "to try without it.")
    turn_secret = fields.Char(
        string="TURN Shared Secret", groups="base.group_system",
        help="The shared secret configured on the TURN server itself "
             "(coturn's static-auth-secret / eturnal's secret) - used "
             "to derive short-lived, per-call TURN credentials here. "
             "Never sent to the browser directly - see "
             "_generate_turn_credentials().")

    def _generate_turn_credentials(self, ttl_seconds=300):
        """A short-lived TURN REST API credential (the scheme both
        coturn and eturnal implement): username is an expiry
        timestamp, password is HMAC-SHA1(secret, username). The
        browser only ever receives this derived, time-limited pair -
        turn_secret itself never leaves the server.
        """
        self.ensure_one()
        if not self.turn_host or not self.turn_secret:
            return False
        expiry = int(time.time()) + ttl_seconds
        username = f'{expiry}:odoo'
        digest = hmac.new(
            self.turn_secret.encode(), username.encode(), hashlib.sha1
        ).digest()
        return {
            'urls': [
                f'turn:{self.turn_host}?transport=udp',
                f'turn:{self.turn_host}?transport=tcp',
            ],
            'username': username,
            'credential': base64.b64encode(digest).decode(),
        }

    sip_domain = fields.Char(
        string="SIP Domain", groups="base.group_system",
        help="The hostname softphones and desk phones register with. "
             "Copy it exactly from the SIP settings in your phone "
             "provider's dashboard (the part of the SIP URI after the "
             "@); it usually can't be worked out from the account "
             "domain.")

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
                "This phone account's SIP Domain isn't set yet. Copy it "
                "from the SIP settings in your phone provider's dashboard."))
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
