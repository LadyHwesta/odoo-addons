# -*- coding: utf-8 -*-
from datetime import timedelta

import pytz

from odoo import _, fields, models
from odoo.exceptions import UserError


class SignalWirePhoneNumber(models.Model):
    _inherit = 'signalwire.phone_number'

    assigned_user_id = fields.Many2one(
        'res.users', string="User",
        help="Which user's SignalWire softphone an inbound call to "
             "this number bridges to when Rings is set to \"A User\". "
             "That user needs a provisioned SignalWire softphone "
             "first (their own user form's Preferences tab).")
    route_type = fields.Selection(
        [('user', "A User"), ('group', "A Call Group")],
        string="Rings", default='user', required=True,
        help="A single user's softphone (and desk phones), or every "
             "member of a shared Call Group at once.")
    call_group_id = fields.Many2one(
        'signalwire.call.group', string="Call Group",
        help="Every member's softphone (and desk phones) rings at "
             "once. Used when Rings is set to \"A Call Group\".")

    calendar_id = fields.Many2one(
        'resource.calendar', string="Business Hours",
        help="Optional. If set, a call arriving outside these hours "
             "uses the After-Hours routing below instead of the "
             "regular one above. Leave blank for a number that "
             "should always route the same way regardless of time.")
    after_hours_route_type = fields.Selection(
        [('user', "A User"), ('group', "A Call Group")],
        string="After-Hours Rings", default='user')
    after_hours_user_id = fields.Many2one('res.users', string="After-Hours User")
    after_hours_call_group_id = fields.Many2one(
        'signalwire.call.group', string="After-Hours Call Group")

    def _is_within_business_hours(self):
        """True if "now" falls inside this number's own Business
        Hours calendar - always True if none is set (a number with
        no calendar is always "open"). Uses resource.calendar's own
        attendance-interval API (the same mechanism core itself uses
        for working-hours checks) rather than a hand-rolled day/time
        comparison, so holiday/leave records already attached to the
        calendar are respected automatically.
        """
        self.ensure_one()
        if not self.calendar_id:
            return True
        now = fields.Datetime.now().replace(tzinfo=pytz.UTC)
        intervals = self.calendar_id._attendance_intervals_batch(
            now, now + timedelta(minutes=1))
        return bool(intervals.get(False))

    def _effective_route(self):
        """(route_type, target) actually in effect right now for this
        number - the day-mode routing fields above, or the after-
        hours ones instead if a Business Hours calendar is set and
        "now" falls outside it. `target` is a res.users or
        signalwire.call.group record (possibly empty, if that side
        was never configured).
        """
        self.ensure_one()
        if self.calendar_id and not self._is_within_business_hours():
            if self.after_hours_route_type == 'group':
                return 'group', self.after_hours_call_group_id
            return 'user', self.after_hours_user_id
        if self.route_type == 'group':
            return 'group', self.call_group_id
        return 'user', self.assigned_user_id

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
        route_type, target = self._effective_route()
        if not target:
            raise UserError(_(
                "Set who or which Call Group %(number)s should ring.", number=self.name))
        if route_type == 'user' and not target.voip_username:
            raise UserError(_(
                "%(user)s doesn't have a SignalWire softphone provisioned yet - "
                "use \"Provision SignalWire Softphone\" on their user form first.",
                user=target.name))
        if route_type == 'group' and not target.member_ids.filtered('voip_username'):
            raise UserError(_(
                "%(group)s has no members with a SignalWire softphone provisioned yet.",
                group=target.name))
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        client = self.subproject_id.server_id._get_client()
        client.compat_post(
            f'Accounts/{self.subproject_id.account_sid}/'
            f'IncomingPhoneNumbers/{self.sid}.json',
            VoiceUrl=f'{base_url}/signalwire/voice/inbound')
