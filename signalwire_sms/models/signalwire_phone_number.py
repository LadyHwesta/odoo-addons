# -*- coding: utf-8 -*-
from odoo import models, fields


class SignalWirePhoneNumber(models.Model):
    _inherit = 'signalwire.phone_number'

    sms_webhook_url = fields.Char(
        string="SMS Forwarding Webhook",
        help="If set, every inbound SMS to this number is also POSTed "
             "here as JSON ({from, to, body, sid, received_at}) - lets "
             "a resold customer plug this number into their own "
             "system instead of (or alongside) Odoo's own chatter "
             "logging/portal page. Self-service - a customer can set "
             "this themselves from their own portal page.")
    sms_ids = fields.One2many('signalwire.sms', 'phone_number_id', string="Messages")
    sms_count = fields.Integer(compute='_compute_sms_count')

    def _compute_sms_count(self):
        for number in self:
            number.sms_count = self.env['signalwire.sms'].search_count(
                [('phone_number_id', '=', number.id)])

    def send_sms(self, to, body):
        """Send one SMS from this number - real money/usage the
        moment this succeeds, same caution as anything else in this
        project that spends real trial credit. Requires this number to
        actually have SMS capability enabled, which (as of December
        2025) needs SignalWire's own Campaign Registry (10DLC) brand +
        campaign registration first - see this module's own README.
        """
        self.ensure_one()
        client = self.subproject_id.server_id._get_client()
        result = client.compat_post(
            f'Accounts/{self.subproject_id.account_sid}/Messages.json',
            From=self.name, To=to, Body=body)
        message = self.env['signalwire.sms'].create({
            'phone_number_id': self.id,
            'direction': 'outbound',
            'from_number': self.name,
            'to_number': to,
            'body': body,
            'sid': result.get('sid'),
            'state': result.get('status'),
        })
        message._log_to_partner_chatter()
        return message
