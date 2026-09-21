# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SignalWireLiveCall(models.Model):
    """A real, currently-in-progress (or just-ended) inbound call -
    distinct from voip_oca's own voip.call (a per-user call *log*
    entry created client-side once a softphone actually answers or
    dials). This record exists the moment SignalWire's own inbound
    webhook fires, tracks the same call_sid throughout its whole
    routing journey (softphone attempt, fallback steps, IVR), and is
    what the live receptionist panel lists and acts on - a panel
    action works by redirecting *this* call's own live cXML flow via
    SignalWire's Compatibility API, never by the receptionist's own
    softphone joining it.
    """
    _name = 'signalwire.live_call'
    _description = 'SignalWire Live Call'
    _order = 'create_date desc'
    _rec_name = 'from_number'

    call_sid = fields.Char(required=True, index=True)
    phone_number_id = fields.Many2one('signalwire.phone_number', required=True)
    company_id = fields.Many2one(related='phone_number_id.company_id', store=True)
    from_number = fields.Char()
    assigned_user_id = fields.Many2one('res.users')
    state = fields.Selection(
        [('ringing', "Ringing"), ('parked', "On Hold (Being Routed)"),
         ('connected', "Connected"), ('ended', "Ended")],
        default='ringing', required=True)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._notify_panel()
        return records

    def write(self, vals):
        result = super().write(vals)
        if 'state' in vals:
            self._notify_panel()
        return result

    def _notify_panel(self):
        """Broadcasts to every connected user who's a member of the
        SignalWire Receptionist group - bus.bus._sendone() requires an
        actual record as its target, and every connected user is
        already auto-subscribed to their own group records
        (ir_websocket._build_bus_channel_list() does this
        unconditionally, confirmed by reading Odoo 19's own source),
        so targeting the group itself reaches every open receptionist
        panel with no extra client-side subscription code needed.
        """
        group = self.env.ref('signalwire_voip_click2call.group_signalwire_receptionist')
        self.env['bus.bus']._sendone(group, 'signalwire_live_call/updated', {})

    def _redirect(self, url):
        """Points this call's own live cXML flow at a new URL via
        SignalWire's Compatibility API "Update a call" endpoint - the
        call keeps ringing/playing whatever that new URL returns, the
        caller never has to hang up and call back. Requires the call
        to still actually be in progress on SignalWire's own side; a
        call SignalWire itself already ended returns a real error
        here, surfaced as-is rather than swallowed. sudo() because a
        receptionist's own group has no access to signalwire.server
        (System-group only, same as every other credential-holding
        record in this project) - this method is the one safe,
        narrow operation it's allowed to trigger.
        """
        self.ensure_one()
        server = self.phone_number_id.sudo().subproject_id.server_id
        client = server._get_client()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        client.compat_post(
            f'Accounts/{self.phone_number_id.sudo().subproject_id.account_sid}/'
            f'Calls/{self.call_sid}.json',
            Url=f'{base_url}{url}')

    def action_route_to_user(self, user_id):
        """Blind route: redirect straight to that user's own SIP
        targets, reusing the exact same fallback chain a normal
        direct-user-routed number already gets if unanswered. Takes a
        plain id (not a recordset) since this is called both from
        Python and, via the receptionist panel, over RPC - browsing
        internally keeps one calling convention for both.
        """
        self.ensure_one()
        user = self.env['res.users'].browse(user_id)
        if not user.voip_username and not user.signalwire_desk_phone_ids.filtered(
                'voip_username'):
            raise UserError(_(
                "%(user)s doesn't have a SignalWire softphone provisioned yet.",
                user=user.name))
        self._redirect(f'/signalwire/voice/route_to_user/{user.id}/{self.phone_number_id.id}')
        self.write({'assigned_user_id': user.id, 'state': 'ringing'})

    def action_park(self):
        """Puts the caller on a "please hold" loop, freeing the
        receptionist to place a normal, separate outbound call to
        check whether a colleague can take it - see this module's own
        README for why this deliberately isn't a 3-way conference
        bridge.
        """
        self.ensure_one()
        self._redirect(f'/signalwire/voice/hold_loop/{self.phone_number_id.id}')
        self.state = 'parked'

    def action_send_to_voicemail(self, user_id):
        self.ensure_one()
        user = self.env['res.users'].browse(user_id)
        self._redirect(
            f'/signalwire/voice/route_to_voicemail/{user.id}/{self.phone_number_id.id}')
        self.write({'assigned_user_id': user.id, 'state': 'ringing'})
