# -*- coding: utf-8 -*-
import re

from odoo import api, fields, models

from odoo.addons.activitypub.models.activitypub_service import (
    AS_PUBLIC,
    to_ap_datetime,
)

_TRIGGER_FIELDS = frozenset({
    'name', 'subtitle', 'description', 'date_begin', 'date_end', 'date_tz',
    'address_id', 'address_inline', 'website_published', 'active',
    'tag_ids', 'event_type_id', 'activitypub_actor_id', 'cover_properties',
})


class EventEvent(models.Model):
    _name = 'event.event'
    _inherit = ['event.event', 'activitypub.federatable']

    activitypub_actor_id = fields.Many2one(
        'activitypub.actor', string='Federate as',
        compute='_compute_activitypub_actor_id', store=True, readonly=False,
        help='The actor whose Fediverse followers are notified about this '
             'event. Defaults from the event category; override per event.')

    @api.depends('event_type_id')
    def _compute_activitypub_actor_id(self):
        """Default from the category into the visible field, but never
        clobber a value already set - a per-event override, or a choice
        made before the category had one. This is a UI convenience only:
        _ap_actor() below has its own live fallback to the category's
        *current* actor whenever this field is empty, so a category fixed
        after an event was created still takes effect for that event even
        though the stored field here is never touched by this compute
        again. action_reset_activitypub_actor makes that same fix visible
        in the field itself, for an event that already has an explicit
        (even if only auto-filled) stored value.
        """
        for event in self:
            if not event.activitypub_actor_id and event.event_type_id.activitypub_actor_id:
                event.activitypub_actor_id = event.event_type_id.activitypub_actor_id

    def action_reset_activitypub_actor(self):
        """Re-apply the event category's Federate-as actor to the visible
        field, overwriting any per-event value. Functionally _ap_actor()
        already falls back to the category live when this field is empty;
        this is for making that explicit/visible, or for overwriting a
        stored value that no longer matches the category on purpose."""
        for event in self:
            if event.event_type_id.activitypub_actor_id:
                event.activitypub_actor_id = event.event_type_id.activitypub_actor_id

    # ------------------------------------------------------------------
    def _ap_trigger_fields(self):
        return _TRIGGER_FIELDS

    @api.model
    def _cron_federate_catch_up(self):
        """Catches an event whose category got its Federate-as actor set
        after the event was already published - that doesn't fire a
        write() on the event itself, so _ap_sync() never re-runs on its
        own."""
        self._ap_catch_up([('website_published', '=', True)])

    def _ap_object_type(self):
        return 'Event'

    def _ap_actor(self):
        self.ensure_one()
        Actor = self.env['activitypub.actor'].sudo()
        # The stored field is an explicit per-event override once set; while
        # it's empty, resolve the category's *current* actor live rather
        # than relying on the compute (which only auto-fills once and never
        # re-fires on the category's own actor changing - see
        # _compute_activitypub_actor_id) - otherwise a category fixed after
        # an event was created would never take effect for that event.
        actor = self.activitypub_actor_id or self.event_type_id.activitypub_actor_id
        return actor if actor.active else Actor.browse()

    def _ap_is_public(self):
        self.ensure_one()
        return bool(self.website_published and getattr(self, 'active', True))

    def _ap_build_object(self, actor):
        self.ensure_one()
        base = actor._base_url()
        path = self.website_url or ('/event/%s' % self.id)
        event = {
            'name': self.name or '',
            'content': self.description or '',
            'mediaType': 'text/html',
            'startTime': to_ap_datetime(self.date_begin),
            'endTime': to_ap_datetime(self.date_end),
            'url': base + path,
            'attributedTo': actor.actor_url,
            'to': [AS_PUBLIC],
            'cc': [actor._endpoint('/followers')],
            'published': to_ap_datetime(self.create_date),
        }
        if self.subtitle:
            event['summary'] = self.subtitle

        place = self._ap_place()
        if place:
            event['location'] = place

        tags = [
            {'type': 'Hashtag', 'name': '#' + re.sub(r'\s+', '', tag.name)}
            for tag in self.tag_ids if tag.name
        ]
        if tags:
            event['tag'] = tags

        cover = self._ap_cover_image_url(base)
        if cover:
            event['attachment'] = [{'type': 'Image', 'url': cover}]
        return event

    def _ap_place(self):
        self.ensure_one()
        address = self.address_id
        name = (address.display_name if address else '') or self.address_inline
        if not name:
            return None
        place = {'type': 'Place', 'name': name}
        # partner_latitude/longitude default to 0.0 (not None/unset) when
        # never geocoded, which is indistinguishable from a genuine (0, 0)
        # by value alone - `date_localization` (base_geolocalize) is only
        # ever set after a real successful geocode, so it is what actually
        # tells the two apart. Absent entirely when base_geolocalize isn't
        # installed, which also correctly skips including coordinates.
        if address and getattr(address, 'date_localization', False):
            place['latitude'] = address.partner_latitude
            place['longitude'] = address.partner_longitude
        return place
