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
        """Default from the category, but never clobber a value already set -
        a per-event override, or a choice made before the category had one."""
        for event in self:
            if not event.activitypub_actor_id and event.event_type_id.activitypub_actor_id:
                event.activitypub_actor_id = event.event_type_id.activitypub_actor_id

    # ------------------------------------------------------------------
    def _ap_trigger_fields(self):
        return _TRIGGER_FIELDS

    def _ap_object_type(self):
        return 'Event'

    def _ap_actor(self):
        self.ensure_one()
        actor = self.activitypub_actor_id
        return actor if actor.active else self.env['activitypub.actor'].browse()

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
