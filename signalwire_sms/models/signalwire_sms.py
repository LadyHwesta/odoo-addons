# -*- coding: utf-8 -*-
import logging

import requests

from odoo import _, api, models, fields

_logger = logging.getLogger(__name__)

WEBHOOK_TIMEOUT = 10


class SignalWireSms(models.Model):
    """One SMS, sent or received, through a SignalWire number - the
    audit trail behind both use cases this module supports (team
    messages logged to a partner's chatter, and a resold customer's
    own message history on their portal page). Not itself a chatter-
    enabled record - the actual chatter message goes on whichever
    res.partner gets matched, via _log_to_partner_chatter().
    """
    _name = 'signalwire.sms'
    _description = 'SignalWire SMS'
    _order = 'create_date desc'
    _rec_name = 'body'

    phone_number_id = fields.Many2one(
        'signalwire.phone_number', required=True, ondelete='cascade',
        help="Which of our SignalWire numbers this message was sent "
             "from or received on.")
    direction = fields.Selection(
        [('outbound', 'Outbound'), ('inbound', 'Inbound')], required=True)
    from_number = fields.Char(required=True)
    to_number = fields.Char(required=True)
    body = fields.Text(required=True)
    sid = fields.Char(string="SID", help="SignalWire's own ID for this message.")
    state = fields.Char(
        help="SignalWire's own delivery status for an outbound message "
             "(queued/sent/delivered/failed/...), or \"received\" for "
             "an inbound one.")
    partner_id = fields.Many2one(
        'res.partner',
        help="Best-effort match against the other party's number - "
             "see _log_to_partner_chatter for how, and its limits.")
    webhook_status = fields.Char(
        readonly=True,
        help="Outcome of forwarding this message to the owning "
             "number's configured webhook, if any - blank if no "
             "webhook is configured, \"forwarded\" on success, or the "
             "error otherwise. For troubleshooting a customer's own "
             "integration, not something they need to act on from "
             "Odoo's side.")

    def _log_to_partner_chatter(self):
        """Best-effort match this message to a res.partner by the
        *other* party's number, and log it as a chatter message there.
        Matching is deliberately loose (last 10 digits, comparing
        digits-only on both sides) rather than an exact string match -
        the same "best-effort, not bulletproof" approach this project
        already takes for phone formatting elsewhere
        (res.partner._namecheap_format_phone), since a partner's own
        ``phone`` field is free text and SignalWire's E.164 format
        won't match it exactly. (Odoo 19 dropped the separate
        ``mobile`` field on res.partner - ``phone`` is the only one
        left to match against.)

        SQL's ``like`` compares against the field's *stored* text
        as-is, punctuation and all - "5556102107" is not a substring
        of the literal string "+1 (555) 610-2107" even though the
        digits match, since ") " and "-" break up the run. So this
        narrows candidates via a ``like`` on just the last 4 digits
        (almost always still contiguous even in a formatted number),
        then does the real comparison in Python against each
        candidate's own digits-only number.
        """
        for message in self:
            other_number = (
                message.to_number if message.direction == 'outbound'
                else message.from_number)
            digits = ''.join(filter(str.isdigit, other_number))[-10:]
            if not digits:
                continue
            last_four = digits[-4:]
            candidates = self.env['res.partner'].search([('phone', 'like', last_four)])
            partner = candidates.filtered(
                lambda p: ''.join(filter(str.isdigit, p.phone or ''))[-10:] == digits
            )[:1]
            if not partner:
                continue
            message.partner_id = partner
            label = _("SMS to %(number)s", number=other_number) if \
                message.direction == 'outbound' else \
                _("SMS from %(number)s", number=other_number)
            partner.message_post(body=f"{label}: {message.body}")

    def _forward_to_customer_webhook(self):
        """Best-effort forward of an inbound message to whatever URL
        the owning number's customer configured (self-service, via
        their portal page) - fire-and-forget, logged on failure rather
        than raised, since a customer's own endpoint being down
        shouldn't break receiving the SMS in Odoo itself.
        """
        for message in self:
            url = message.phone_number_id.sms_webhook_url
            if not url:
                continue
            try:
                requests.post(url, json={
                    'from': message.from_number,
                    'to': message.to_number,
                    'body': message.body,
                    'sid': message.sid,
                    'received_at': fields.Datetime.to_string(message.create_date),
                }, timeout=WEBHOOK_TIMEOUT)
            except requests.RequestException as exc:
                _logger.warning(
                    "SignalWire: failed to forward inbound SMS %s to %s: %s",
                    message.id, url, exc)
                message.webhook_status = str(exc)
            else:
                message.webhook_status = 'forwarded'
