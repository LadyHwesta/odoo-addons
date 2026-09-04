# -*- coding: utf-8 -*-
import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class ActivityPubObject(models.Model):
    """A federated object - one per thing that has been (or was) published.

    Local objects (``local = True``) are the canonical copy of an Odoo record
    rendered as ActivityStreams, addressed by ``.../ap/objects/<id>``. Remote
    objects are stored from Phase 3 onward so replies and boosts can be
    threaded.
    """
    _name = 'activitypub.object'
    _description = 'ActivityPub Object'
    _rec_name = 'uri'
    _order = 'id desc'

    uri = fields.Char(required=True, index=True, copy=False)
    object_type = fields.Char(string='Type', help='Note, Article, Event, ...')
    actor_id = fields.Many2one(
        'activitypub.actor', string='Attributed To', ondelete='cascade', index=True)
    local = fields.Boolean(
        default=False, index=True,
        help='True when this is our own record rendered for federation.')
    published = fields.Datetime(copy=False)
    deleted = fields.Boolean(
        default=False, copy=False,
        help='Tombstoned: a Delete has been (or is being) sent for it.')

    source_model = fields.Char(index=True)
    source_res_id = fields.Many2oneReference(
        model_field='source_model', string='Source Record', index=True)

    in_reply_to_uri = fields.Char(string='In Reply To')
    payload = fields.Json(help='The object exactly as served / received.')

    _uri_uniq = models.Constraint('unique(uri)', 'That object URI already exists.')

    def _human_url(self):
        """Where a browser hitting the object URL should be redirected - the
        Odoo web page for the underlying record when there is one."""
        self.ensure_one()
        if self.source_model and self.source_res_id:
            record = self.env[self.source_model].browse(self.source_res_id).exists()
            page = record and getattr(record, 'website_url', False)
            if page:
                return record.get_base_url() + page
        if self.actor_id:
            return self.actor_id._base_url() or '/'
        return '/'
