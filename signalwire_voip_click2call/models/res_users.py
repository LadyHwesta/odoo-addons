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

    signalwire_forwarding_number_ids = fields.One2many(
        'signalwire.forwarding.number', 'user_id', string="Saved Numbers")
    signalwire_desk_phone_ids = fields.One2many(
        'signalwire.desk_phone', 'user_id', string="Desk Phones",
        help="Physical SIP desk phones registered to this user - each "
             "rings alongside the softphone on an inbound call, using "
             "its own separate SignalWire SIP Endpoint.")
    signalwire_active_forward_id = fields.Many2one(
        'signalwire.forwarding.number', string="Forward Calls To",
        domain="[('user_id', '=', id)]",
        help="If set, an inbound call that doesn't reach the softphone "
             "in time rings this number next. Self-service, and meant "
             "to be changed on the fly (e.g. before stepping away from "
             "the desk) - not an admin-only setting.")
    signalwire_ring_group_ids = fields.Many2many(
        'res.users', 'signalwire_ring_group_rel', 'user_id', 'teammate_id',
        string="Also Ring",
        help="Teammates to ring (all at once) if this user's softphone "
             "and forwarding number (if any) don't answer. Only "
             "teammates with their own softphone already provisioned "
             "actually get rung - see this module's own README.")
    signalwire_voicemail_enabled = fields.Boolean(
        default=True,
        help="Take a voicemail if nothing above answers - the "
             "guaranteed last resort so a caller is never just "
             "dropped. Recordings get attached to the matched "
             "contact's chatter, if any, and always schedule a "
             "\"return this call\" activity for this user either way.")
    signalwire_voicemail_transcribe = fields.Boolean(
        default=True,
        help="Also ask SignalWire to transcribe each voicemail (a "
             "paid add-on on their end, billed per recording) so the "
             "text shows up right in the voicemail systray, letting "
             "you decide whether it's worth listening to in full "
             "before you do. Turn off to only ever get the audio.")

    def action_use_profile_phone_as_forward(self):
        """Convenience: seed a saved number straight from this user's
        own partner profile phone, rather than requiring it to be
        retyped - the "use my account's own phone info" shortcut.
        """
        self.ensure_one()
        if not self.partner_id.phone:
            raise UserError(_(
                "%(user)s's own profile has no phone number set.", user=self.name))
        existing = self.signalwire_forwarding_number_ids.filtered(
            lambda n: n.phone_number == self.partner_id.phone)
        if existing:
            return existing[0]
        return self.env['signalwire.forwarding.number'].create({
            'user_id': self.id, 'name': 'Profile Phone',
            'phone_number': self.partner_id.phone,
        })

    def _signalwire_match_partner(self, other_number):
        """Best-effort digits-only match, same approach (and same
        SQL-LIKE-can't-see-past-punctuation reasoning) as
        signalwire_sms's own _log_to_partner_chatter - duplicated
        rather than shared since this module doesn't depend on
        signalwire_sms.
        """
        digits = ''.join(filter(str.isdigit, other_number or ''))[-10:]
        if not digits:
            return self.env['res.partner']
        last_four = digits[-4:]
        candidates = self.env['res.partner'].search([('phone', 'like', last_four)])
        return candidates.filtered(
            lambda p: ''.join(filter(str.isdigit, p.phone or ''))[-10:] == digits
        )[:1]

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
