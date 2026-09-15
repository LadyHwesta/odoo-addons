# -*- coding: utf-8 -*-
from odoo import _, api, models, fields
from odoo.exceptions import UserError


class SignalWireSmsCompose(models.TransientModel):
    _name = 'signalwire.sms.compose'
    _description = 'Send an SMS via SignalWire'

    partner_id = fields.Many2one('res.partner', required=True)
    phone_number_id = fields.Many2one(
        'signalwire.phone_number', string="From", required=True,
        help="Which of our SignalWire numbers to send from.")
    to = fields.Char(required=True)
    body = fields.Text(required=True)

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        if 'phone_number_id' in fields_list and not values.get('phone_number_id'):
            # Default to a number that isn't dedicated to a resold
            # customer - team messaging should send from "our own"
            # number(s), not one whose usage a customer is being
            # billed for.
            default_number = self.env['signalwire.phone_number'].search(
                [('subproject_id.partner_id', '=', False)], limit=1)
            values['phone_number_id'] = default_number.id
        return values

    def action_send(self):
        self.ensure_one()
        if not self.phone_number_id:
            raise UserError(_("Choose which SignalWire number to send from."))
        self.phone_number_id.send_sms(self.to, self.body)
        return {'type': 'ir.actions.act_window_close'}
