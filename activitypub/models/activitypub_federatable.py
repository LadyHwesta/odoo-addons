# -*- coding: utf-8 -*-
"""Mixin that turns an Odoo record into a federated object.

A bridge module mixes this into a content model
(``_inherit = ['blog.post', 'activitypub.federatable']``) and implements
the four hooks:

* ``_ap_actor()`` - the ``activitypub.actor`` to publish through (empty
  recordset to not federate);
* ``_ap_is_public()`` - whether the record is currently visible enough to
  federate;
* ``_ap_object_type()`` - the ActivityStreams type (``Article``,
  ``Event``, ...);
* ``_ap_build_object(actor)`` - the object body as a dict.

The mixin owns the create / write / unlink plumbing and the publish /
update / retract decision, so the bridges stay tiny and behave alike.
"""
import json
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class ActivityPubFederatable(models.AbstractModel):
    _name = 'activitypub.federatable'
    _description = 'Federatable Record'

    # ------------------------------------------------------------------
    # Hooks - overridden by the concrete model
    # ------------------------------------------------------------------
    def _ap_actor(self):
        return self.env['activitypub.actor'].browse()

    def _ap_is_public(self):
        return False

    def _ap_object_type(self):
        return 'Note'

    def _ap_build_object(self, actor):
        return {}

    def _ap_trigger_fields(self):
        """Field names whose ``write`` should re-federate the record."""
        return frozenset()

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------
    def _ap_cover_image_url(self, base_url):
        """Absolute URL of the record's cover image, from the
        ``website.cover_properties.mixin`` JSON, or ``None``."""
        self.ensure_one()
        raw = getattr(self, 'cover_properties', None)
        if not raw:
            return None
        try:
            background = (json.loads(raw) or {}).get('background-image') or 'none'
        except (ValueError, TypeError):
            return None
        if not background or background == 'none':
            return None
        url = background
        if background.startswith('url('):
            url = background[4:-1].strip('"\'')
        if not url:
            return None
        if url.startswith(('http://', 'https://')):
            return url
        return base_url + url

    # ------------------------------------------------------------------
    # Publish / update / retract decision
    # ------------------------------------------------------------------
    def _ap_sync(self, retract=False):
        if self.env.context.get('activitypub_no_sync'):
            return
        Object = self.env['activitypub.object'].sudo()
        for record in self:
            existing = Object.search([
                ('source_model', '=', record._name),
                ('source_res_id', '=', record.id),
            ], limit=1)
            live = bool(existing) and not existing.deleted
            actor = record._ap_actor()
            should_publish = (not retract) and record._ap_is_public() and bool(actor)

            if not should_publish:
                if live and existing.actor_id:
                    existing.actor_id._ap_retract(record._name, record.id)
                continue

            # Attribution moved to a different actor: retract from the old
            # one, start fresh on the new.
            if live and existing.actor_id and existing.actor_id != actor:
                existing.actor_id._ap_retract(record._name, record.id)
                live = False

            actor._ap_publish(
                record._name, record.id, record._ap_object_type(),
                record._ap_build_object(actor),
                activity_type='Update' if live else 'Create')

    # ------------------------------------------------------------------
    # ORM plumbing
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._ap_sync()
        return records

    def write(self, vals):
        res = super().write(vals)
        if self._ap_trigger_fields().intersection(vals):
            self._ap_sync()
        return res

    def unlink(self):
        # Retract while the records (and their ids) still exist.
        self._ap_sync(retract=True)
        return super().unlink()
