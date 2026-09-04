# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ActivityPubInteraction(models.Model):
    """A remote Like or Announce (boost) of one of our local objects.

    Kept as its own small row - rather than only an ``activitypub.activity``
    log entry - so an ``Undo`` can remove exactly the right one and the
    per-object counters stay a cheap group-by.
    """
    _name = 'activitypub.interaction'
    _description = 'ActivityPub Interaction'
    _rec_name = 'actor_uri'
    _order = 'id desc'

    object_id = fields.Many2one(
        'activitypub.object', required=True, ondelete='cascade', index=True)
    actor_uri = fields.Char(string='Remote Actor', required=True, index=True)
    interaction_type = fields.Selection([
        ('like', 'Like'),
        ('announce', 'Announce'),
    ], required=True)
    activity_uri = fields.Char(string='Activity', help='Id of the Like / Announce.')

    _obj_actor_type_uniq = models.Constraint(
        'unique(object_id, actor_uri, interaction_type)',
        'That actor has already reacted to this object.',
    )

    @api.model
    def _record_reaction(self, local_object, actor_uri, interaction_type, activity_uri):
        existing = self.search([
            ('object_id', '=', local_object.id),
            ('actor_uri', '=', actor_uri),
            ('interaction_type', '=', interaction_type),
        ], limit=1)
        if existing:
            if activity_uri and existing.activity_uri != activity_uri:
                existing.activity_uri = activity_uri
            return existing
        return self.create({
            'object_id': local_object.id,
            'actor_uri': actor_uri,
            'interaction_type': interaction_type,
            'activity_uri': activity_uri,
        })

    @api.model
    def _drop_reaction(self, actor_uri, interaction_type, object_uri=None):
        domain = [
            ('actor_uri', '=', actor_uri),
            ('interaction_type', '=', interaction_type),
        ]
        if object_uri:
            domain.append(('object_id.uri', '=', object_uri))
        gone = self.search(domain)
        count = len(gone)
        gone.unlink()
        return count
