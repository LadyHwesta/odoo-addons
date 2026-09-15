# -*- coding: utf-8 -*-
from odoo import models, fields


class SignalWirePhoneNumber(models.Model):
    """A phone number actually purchased into a subproject. Release is
    a real, billable-going-forward change (frees the number back to
    SignalWire, stops its monthly charge) - not undoable from Odoo's
    side once done, same class of one-way action as HestiaCP account
    termination.
    """
    _name = 'signalwire.phone_number'
    _description = 'SignalWire Phone Number'
    _rec_name = 'name'

    name = fields.Char(string="Phone Number", required=True, help="E.164 format.")
    sid = fields.Char(
        string="SID", required=True,
        help="SignalWire's own ID for this number - needed to release it.")
    subproject_id = fields.Many2one(
        'signalwire.subproject', required=True, ondelete='cascade')
    partner_id = fields.Many2one(
        related='subproject_id.partner_id', store=True, string="Customer")
    active = fields.Boolean(default=True)

    def action_release(self):
        self.ensure_one()
        client = self.subproject_id.server_id._get_client()
        client.compat_delete(
            f'Accounts/{self.subproject_id.account_sid}/'
            f'IncomingPhoneNumbers/{self.sid}.json')
        self.active = False
