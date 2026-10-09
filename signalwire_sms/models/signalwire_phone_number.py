# -*- coding: utf-8 -*-
from odoo import _, models, fields
from odoo.exceptions import UserError

DEFAULT_STOP_REPLY = (
    "You have been unsubscribed and will no longer receive messages "
    "from this number. Reply START to resubscribe.")
DEFAULT_HELP_REPLY = (
    "This number sends account/service messages. Reply STOP to "
    "unsubscribe, or contact us directly for help.")


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
    sms_stop_reply_text = fields.Text(
        string="STOP/START Reply", default=DEFAULT_STOP_REPLY,
        help="Sent back automatically when someone replies STOP "
             "(confirming they're unsubscribed) or START/UNSTOP "
             "(confirming they're resubscribed) to this number.")
    sms_help_reply_text = fields.Text(
        string="HELP Reply", default=DEFAULT_HELP_REPLY,
        help="Sent back automatically when someone replies HELP to "
             "this number - name your own support contact here.")

    def _compute_sms_count(self):
        for number in self:
            number.sms_count = self.env['signalwire.sms'].search_count(
                [('phone_number_id', '=', number.id)])

    def _sms_blocked_partner(self, to):
        """The res.partner this `to` number resolves to, if any, using
        the exact same best-effort digits-only matching
        signalwire.sms._log_to_partner_chatter already uses for an
        *inbound* message's other party - reused here so send_sms can
        check the same match before an *outbound* send.
        """
        digits = ''.join(filter(str.isdigit, to or ''))[-10:]
        if not digits:
            return self.env['res.partner']
        last_four = digits[-4:]
        candidates = self.env['res.partner'].search([('phone', 'like', last_four)])
        return candidates.filtered(
            lambda p: ''.join(filter(str.isdigit, p.phone or ''))[-10:] == digits
        )[:1]

    def send_sms(self, to, body):
        """Send one SMS from this number - real money/usage the
        moment this succeeds, same caution as anything else in this
        project that spends real trial credit. Requires this number to
        actually have SMS capability enabled, which (as of December
        2025) needs SignalWire's own Campaign Registry (10DLC) brand +
        campaign registration first - see this module's own README.

        Refuses outright (raises, doesn't silently no-op) if `to`
        matches a partner who has replied STOP - SignalWire itself
        doesn't enforce this for us (confirmed against their own
        docs), so this is the one real enforcement point. A loud
        failure here is deliberate: swallowing a compliance block
        quietly is worse than a visible one a human notices.
        """
        self.ensure_one()
        blocked = self._sms_blocked_partner(to)
        if blocked and blocked.sms_blocked:
            raise UserError(_(
                "%(partner)s has opted out of SMS (replied STOP) - "
                "refusing to send.", partner=blocked.name))
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
