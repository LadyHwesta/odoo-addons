# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SignalWireCallbackRequest(models.Model):
    """A portal customer's request for a support callback - distinct
    from signalwire.live_call, which represents a real, already-in-
    progress call keyed by a live SignalWire call_sid. A callback
    request has no call in progress yet; conflating the two would
    mean an awkward nullable call_sid and two different lifecycles
    jammed into one model.
    """
    _name = 'signalwire.callback_request'
    _description = 'SignalWire Portal Callback Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    _rec_name = 'phone_number'

    partner_id = fields.Many2one('res.partner', required=True, index=True)
    phone_number = fields.Char(required=True)
    note = fields.Text()
    state = fields.Selection(
        [('pending', "Pending"), ('claimed', "Claimed"), ('completed', "Completed")],
        default='pending', required=True, tracking=True)
    claimed_by_user_id = fields.Many2one('res.users', tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        requests = super().create(vals_list)
        requests._notify_panel()
        for request in requests:
            request.message_post(body=_(
                "New callback request from %(partner)s - %(number)s",
                partner=request.partner_id.name, number=request.phone_number))
        return requests

    def _notify_panel(self):
        """Same mechanism signalwire.live_call already uses - targets
        the Receptionist group record directly (bus.bus._sendone()
        requires an actual record, not a plain string), reaching
        every open receptionist panel with no extra client-side
        subscription code, since every connected user is already
        auto-subscribed to their own group records.
        """
        group = self.env.ref('signalwire_voip_click2call.group_signalwire_receptionist')
        self.env['bus.bus']._sendone(group, 'signalwire_live_call/updated', {})

    def action_claim(self):
        self.ensure_one()
        if self.state != 'pending':
            raise UserError(_("This request has already been claimed."))
        self.write({'state': 'claimed', 'claimed_by_user_id': self.env.uid})
        self.activity_schedule(
            'mail.mail_activity_data_todo', user_id=self.env.uid,
            summary=_("Call back %(partner)s", partner=self.partner_id.name),
            note=_("Requested number: %(number)s", number=self.phone_number))
        self._notify_panel()

    def action_complete(self):
        self.ensure_one()
        self.state = 'completed'
        self.activity_ids.filtered(lambda a: a.user_id == self.env.user).action_done()
        self._notify_panel()
