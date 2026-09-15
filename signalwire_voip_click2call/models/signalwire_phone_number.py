# -*- coding: utf-8 -*-
from odoo import _, models, fields
from odoo.exceptions import UserError


class SignalWirePhoneNumber(models.Model):
    _inherit = 'signalwire.phone_number'

    assigned_user_id = fields.Many2one(
        'res.users', string="Rings",
        help="Which user's SignalWire softphone an inbound call to "
             "this number bridges to. That user needs a provisioned "
             "SignalWire softphone first (their own user form's "
             "Preferences tab).")

    def action_configure_inbound_routing(self):
        """Points this number's Voice URL at this database's own
        /signalwire/voice/inbound webhook - a standard Twilio-
        compatible mechanism (SignalWire POSTs call details there on
        every inbound call, expecting cXML back; well-documented,
        unlike several other things in this project, so not something
        that needed live-verification the way the SIP/WSS hostname
        did). Requires web.base.url to actually be a public, reachable
        HTTPS address - a local dev instance can save this, but
        SignalWire obviously can't reach it until this Odoo is
        actually public.
        """
        self.ensure_one()
        if not self.assigned_user_id:
            raise UserError(_(
                "Set which user %(number)s should ring first.", number=self.name))
        if not self.assigned_user_id.voip_username:
            raise UserError(_(
                "%(user)s doesn't have a SignalWire softphone provisioned yet - "
                "use \"Provision SignalWire Softphone\" on their user form first.",
                user=self.assigned_user_id.name))
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        client = self.subproject_id.server_id._get_client()
        client.compat_post(
            f'Accounts/{self.subproject_id.account_sid}/'
            f'IncomingPhoneNumbers/{self.sid}.json',
            VoiceUrl=f'{base_url}/signalwire/voice/inbound')
