# -*- coding: utf-8 -*-
from odoo import _, models, fields
from odoo.exceptions import UserError

DEFAULT_STOP_REPLY = (
    "You have been unsubscribed and will no longer receive messages "
    "from this number. Reply START to resubscribe.")
DEFAULT_START_REPLY = (
    "You're subscribed again to messages from this number. Reply HELP "
    "for help or STOP to unsubscribe.")
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
        string="STOP Reply", default=DEFAULT_STOP_REPLY,
        help="Sent back automatically when someone replies STOP, "
             "confirming they're unsubscribed.")
    sms_start_reply_text = fields.Text(
        string="START Reply", default=DEFAULT_START_REPLY,
        help="Sent back automatically when someone replies START or "
             "UNSTOP, confirming they're subscribed again. (Until "
             "2026-11-09 START wrongly got the STOP reply.)")
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

    def action_configure_inbound_sms(self):
        """Points this number's incoming-message webhook at this
        database's /signalwire/sms/inbound, the messaging twin of
        signalwire_voip_click2call's action_configure_inbound_routing.

        Until 2026-11-09 nothing set this: the number had a Voice URL but
        no SMS URL, so SignalWire never passed inbound texts to Odoo and
        carrier-mandated HELP/STOP replies silently never happened.
        """
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
        if not base_url.startswith('https://'):
            raise UserError(_(
                "SignalWire can only reach a public HTTPS address, and this "
                "database's web.base.url is %(url)s.", url=base_url or _("not set")))
        client = self.subproject_id.server_id._get_client()
        client.compat_post(
            f'Accounts/{self.subproject_id.account_sid}/IncomingPhoneNumbers/{self.sid}.json',
            SmsUrl=f'{base_url}/signalwire/sms/inbound', SmsMethod='POST')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Incoming messages connected"),
                'message': _(
                    "Texts to %(number)s now come into Odoo at %(url)s.",
                    number=self.name, url=f'{base_url}/signalwire/sms/inbound'),
                'type': 'success',
                'sticky': False,
            },
        }
