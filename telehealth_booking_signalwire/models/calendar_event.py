# -*- coding: utf-8 -*-
import uuid

from odoo import fields, models


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    signalwire_room_name = fields.Char(
        readonly=True, copy=False,
        help="This event's own SignalWire Video room, provisioned the "
             "first time a premium video link is actually requested "
             "for it - not at booking-creation time, so a booking "
             "that never gets a link requested never creates one.")
    signalwire_room_id = fields.Char(
        string="SignalWire Room ID", readonly=True, copy=False,
        help="SignalWire's own ID for the room - needed to release it.")

    def _get_premium_video_url(self):
        """Overrides telehealth_booking's own no-op hook. Returns an
        Odoo-hosted join URL (stable, like Discuss's own
        calendar/join_videocall/<token> route) rather than a raw
        SignalWire link with a baked-in room token - a JWT token
        generated now could expire before the actual appointment
        happens days later; the real token gets generated fresh at
        click time by the join controller instead, same principle
        Discuss's own route already uses.
        """
        self.ensure_one()
        if not self.signalwire_room_name:
            self._provision_signalwire_room()
        if not self.signalwire_room_name:
            return False
        if not self.access_token:
            self.access_token = uuid.uuid4().hex
        return f"{self.get_base_url()}/telehealth/signalwire/join/{self.access_token}"

    def _provision_signalwire_room(self):
        self.ensure_one()
        server = self.env['signalwire.server'].search([], limit=1)
        if not server:
            return
        room_name = f"telehealth-{self.id}-{uuid.uuid4().hex[:8]}"
        result = server._get_client().video_post('rooms', name=room_name)
        self.write({
            'signalwire_room_name': room_name,
            'signalwire_room_id': result['id'],
        })
        self.user_id._ensure_telehealth_video_billing()
