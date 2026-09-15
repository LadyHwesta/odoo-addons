# -*- coding: utf-8 -*-
from odoo import models


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    def _set_discuss_videocall_location(self):
        """The real, standalone entry point core uses to give an
        event a Discuss video link (confirmed by reading
        calendar_event.py directly - the client-facing
        "Add a video call" button is actually a frontend-JS stub;
        this method is what it, and the auto-compute chain, both
        eventually call). Overridden here as the one hook point that
        matters: premium-tier organizers get a real chance to
        provision something better first, with Discuss as the
        guaranteed fallback either way - the base module alone always
        falls straight through to it since _get_premium_video_url
        returns nothing on its own.

        Core's own implementation reads self.access_token directly,
        which only works for a single record - it's always called
        from a per-record loop (_compute_videocall_location's own
        `for event in self:`), never batched. This override has to
        match that same one-at-a-time contract rather than assume
        super() is batch-safe (it isn't - confirmed the hard way, by
        a test passing two records through this at once).
        """
        for event in self:
            url = False
            if event.user_id.telehealth_video_tier == 'premium':
                url = event._get_premium_video_url()
            if url:
                event.videocall_location = url
            else:
                super(CalendarEvent, event)._set_discuss_videocall_location()

    def _get_premium_video_url(self):
        """Hook: return a premium video join URL for this event, or a
        falsy value to fall back to Discuss. No-op in this module -
        overridden by telehealth_booking_signalwire.
        """
        self.ensure_one()
        return False

    def action_get_telehealth_video_link(self):
        """Explicit entry point for a "Get Video Link" button - not
        relying on core's own automatic compute trigger, which is
        driven by frontend JS in normal Calendar UI use
        (videocall_source's own computation is circular on a brand
        new event otherwise) and isn't a reliable thing to depend on
        from server-side code.
        """
        self.ensure_one()
        self._set_discuss_videocall_location()
