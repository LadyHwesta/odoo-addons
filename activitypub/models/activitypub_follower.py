# -*- coding: utf-8 -*-
from odoo import fields, models


class ActivityPubFollower(models.Model):
    """A remote actor that follows one of our local actors. Created when a
    signed ``Follow`` is accepted, removed on ``Undo{Follow}``."""
    _name = 'activitypub.follower'
    _description = 'ActivityPub Follower'
    _rec_name = 'follower_uri'
    _order = 'create_date desc'

    actor_id = fields.Many2one(
        'activitypub.actor', string='Followed Actor', required=True,
        ondelete='cascade', index=True)
    follower_uri = fields.Char(
        string='Follower', required=True, index=True,
        help='The remote actor id URI.')
    inbox_url = fields.Char(help='The follower\'s personal inbox.')
    shared_inbox_url = fields.Char(
        help='The follower\'s server-wide shared inbox, preferred for delivery '
             'because it collapses many followers on one server into a single '
             'POST.')
    follow_activity_uri = fields.Char(
        string='Follow Activity',
        help='Id of the Follow we accepted - echoed back in the Accept.')
    state = fields.Selection([
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
    ], default='accepted', required=True)

    _actor_follower_uniq = models.Constraint(
        'unique(actor_id, follower_uri)',
        'That actor is already recorded as a follower.',
    )

    def _target_inbox(self):
        self.ensure_one()
        return self.shared_inbox_url or self.inbox_url
