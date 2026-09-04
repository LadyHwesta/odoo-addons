# -*- coding: utf-8 -*-
import logging

from markupsafe import Markup

from odoo import api, fields, models
from odoo.tools import html_sanitize

_logger = logging.getLogger(__name__)


def replies_to_chatter(env):
    """Whether an inbound reply should be posted to the source record's
    chatter. Default on: only an explicit 'False' turns it off."""
    return env['ir.config_parameter'].sudo().get_param(
        'activitypub.replies_to_chatter', 'True') != 'False'


class ActivityPubObject(models.Model):
    """A federated object - one per thing that has been (or was) published.

    Local objects (``local = True``) are the canonical copy of an Odoo record
    rendered as ActivityStreams, addressed by ``.../ap/objects/<id>``. Remote
    objects are stored when they interact with a local one (a reply), so
    replies and reactions can be threaded and counted.
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
        help='Tombstoned: a Delete has been (or was) sent / received for it.')

    source_model = fields.Char(index=True)
    source_res_id = fields.Many2oneReference(
        model_field='source_model', string='Source Record', index=True)

    in_reply_to_uri = fields.Char(string='In Reply To', index=True)
    payload = fields.Json(help='The object exactly as served / received.')

    interaction_ids = fields.One2many('activitypub.interaction', 'object_id')

    reply_count = fields.Integer(compute='_compute_engagement')
    like_count = fields.Integer(compute='_compute_engagement')
    announce_count = fields.Integer(compute='_compute_engagement')

    _uri_uniq = models.Constraint('unique(uri)', 'That object URI already exists.')

    # ------------------------------------------------------------------
    def _compute_engagement(self):
        uris = [u for u in self.mapped('uri') if u]
        reply_map = {}
        if uris:
            for parent_uri, count in self.env['activitypub.object']._read_group(
                    [('in_reply_to_uri', 'in', uris), ('deleted', '=', False)],
                    ['in_reply_to_uri'], ['__count']):
                reply_map[parent_uri] = count
        inter_map = {}
        if self.ids:
            for obj, kind, count in self.env['activitypub.interaction']._read_group(
                    [('object_id', 'in', self.ids)],
                    ['object_id', 'interaction_type'], ['__count']):
                inter_map[(obj.id, kind)] = count
        for record in self:
            record.reply_count = reply_map.get(record.uri, 0)
            record.like_count = inter_map.get((record.id, 'like'), 0)
            record.announce_count = inter_map.get((record.id, 'announce'), 0)

    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    def _ap_on_reply(self, reply_object, remote_actor):
        """Post an inbound federated reply to the source record's chatter,
        when the source record is a mail thread and the feature is enabled."""
        self.ensure_one()
        if not replies_to_chatter(self.env):
            return
        if not self.source_model or not self.source_res_id:
            return
        record = self.env[self.source_model].browse(self.source_res_id).exists()
        if not record or not hasattr(record, 'message_post'):
            return

        payload = reply_object.payload or {}
        if remote_actor.preferred_username and remote_actor.domain:
            who = f'@{remote_actor.preferred_username}@{remote_actor.domain}'
        else:
            who = remote_actor.uri
        source_link = payload.get('url') or reply_object.uri
        content = html_sanitize(payload.get('content') or '')
        body = Markup(
            '<p><a href="%s" target="_blank" rel="noreferrer">%s</a> '
            'replied from the Fediverse:</p>%s'
        ) % (source_link, who, Markup(content))
        record.message_post(
            body=body,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
            email_from=who,
        )
