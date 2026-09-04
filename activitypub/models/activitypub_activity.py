# -*- coding: utf-8 -*-
import logging
import uuid

from odoo import api, fields, models

from .activitypub_service import (
    ActivityPubError,
    SignatureError,
    build_accept,
    verify_signature,
)

_logger = logging.getLogger(__name__)

ACTIVITY_TYPES = [
    ('Create', 'Create'),
    ('Update', 'Update'),
    ('Delete', 'Delete'),
    ('Follow', 'Follow'),
    ('Accept', 'Accept'),
    ('Reject', 'Reject'),
    ('Undo', 'Undo'),
    ('Like', 'Like'),
    ('Announce', 'Announce'),
    ('Other', 'Other'),
]


class ActivityPubActivity(models.Model):
    """One ActivityStreams activity, inbound or outbound.

    Outbound rows are the logical unit of publication; the physical POSTs are
    ``activitypub.delivery`` children, one per recipient inbox. Inbound rows
    are a record of what we received and how we handled it.
    """
    _name = 'activitypub.activity'
    _description = 'ActivityPub Activity'
    _rec_name = 'uri'
    _order = 'id desc'

    uri = fields.Char(required=True, index=True, copy=False)
    activity_type = fields.Selection(ACTIVITY_TYPES, string='Type', required=True)
    direction = fields.Selection([
        ('out', 'Outbound'),
        ('in', 'Inbound'),
    ], required=True, index=True)

    actor_id = fields.Many2one(
        'activitypub.actor', string='Local Actor', ondelete='cascade', index=True,
        help='The local actor this activity is from (outbound) or for (inbound).')
    remote_actor_uri = fields.Char(
        string='Remote Actor', help='Set on inbound activities.')
    object_id = fields.Many2one(
        'activitypub.object', string='Object', ondelete='set null')
    object_uri = fields.Char(
        help='Raw object URI when it is not one of our stored objects '
             '(a Follow target, a Like of our post, ...).')

    state = fields.Selection([
        ('pending', 'Pending'),
        ('delivering', 'Delivering'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('received', 'Received'),
        ('processed', 'Processed'),
        ('ignored', 'Ignored'),
    ], default='pending', index=True, copy=False)
    payload = fields.Json(copy=False)

    delivery_ids = fields.One2many('activitypub.delivery', 'activity_id')

    _uri_uniq = models.Constraint('unique(uri)', 'That activity URI already exists.')

    # ------------------------------------------------------------------
    # Outbound
    # ------------------------------------------------------------------
    def _queue_deliveries(self, inbox_urls):
        """Create one pending delivery per distinct inbox for this activity."""
        self.ensure_one()
        Delivery = self.env['activitypub.delivery'].sudo()
        existing = set(self.delivery_ids.mapped('inbox_url'))
        to_add = [url for url in inbox_urls if url and url not in existing]
        if to_add:
            Delivery.create([
                {'activity_id': self.id, 'inbox_url': url} for url in to_add
            ])
        if self.state == 'pending' and not to_add and not self.delivery_ids:
            # Nothing to deliver (no followers yet) - it still belongs in the
            # outbox, so mark it done rather than leaving it 'pending'.
            self.state = 'delivered'
        return self.delivery_ids

    # ------------------------------------------------------------------
    # Inbound
    # ------------------------------------------------------------------
    @api.model
    def _ingest(self, raw, headers, request_path, body_bytes, target_actor=None):
        """Verify an inbound activity's HTTP Signature and dispatch it.

        Returns the HTTP status the inbox controller should send back. Never
        raises: a bad activity is a logged ``202``/``401``, not a 500.
        """
        actor_uri = raw.get('actor')
        if isinstance(actor_uri, dict):
            actor_uri = actor_uri.get('id')
        atype = raw.get('type')
        if not actor_uri or not atype:
            return 400

        RemoteActor = self.env['activitypub.remote.actor'].sudo()
        try:
            remote = RemoteActor._get(actor_uri)
        except ActivityPubError as exc:
            _logger.info('Inbound %s: cannot dereference actor %s (%s)',
                         atype, actor_uri, exc)
            return 401
        if not remote.public_key_pem:
            _logger.info('Inbound %s: actor %s has no public key', atype, actor_uri)
            return 401

        try:
            sig = verify_signature('post', request_path, headers, body_bytes,
                                   remote.public_key_pem)
        except SignatureError as exc:
            _logger.info('Inbound %s from %s: bad signature (%s)',
                         atype, actor_uri, exc)
            return 401

        key_id = (sig.get('keyId') or '').split('#')[0]
        if key_id and key_id != actor_uri and key_id != (remote.uri or ''):
            _logger.info('Inbound %s: keyId %s does not belong to actor %s',
                         atype, sig.get('keyId'), actor_uri)
            return 401

        handler = getattr(self, f'_ingest_{atype.lower()}', None)
        if handler is None:
            _logger.info('Inbound %s from %s: no handler, accepted and ignored',
                         atype, actor_uri)
            self._record_inbound(raw, remote, target_actor, state='ignored')
            return 202
        return handler(raw, remote, target_actor)

    def _record_inbound(self, raw, remote, target_actor, state='received'):
        vals = {
            'uri': raw.get('id') or f'urn:inbound:{remote.uri}:{fields.Datetime.now()}',
            'activity_type': raw.get('type') if raw.get('type') in dict(ACTIVITY_TYPES) else 'Other',
            'direction': 'in',
            'remote_actor_uri': remote.uri,
            'actor_id': target_actor.id if target_actor else False,
            'object_uri': self._object_uri(raw.get('object')),
            'state': state,
            'payload': raw,
        }
        existing = self.search([('uri', '=', vals['uri']), ('direction', '=', 'in')], limit=1)
        if existing:
            return existing
        return self.create(vals)

    @staticmethod
    def _object_uri(obj):
        if isinstance(obj, dict):
            return obj.get('id')
        if isinstance(obj, str):
            return obj
        return False

    def _ingest_follow(self, raw, remote, target_actor):
        target_uri = self._object_uri(raw.get('object'))
        local = target_actor or self.env['activitypub.actor'].sudo()._for_url(target_uri)
        if not local:
            return 404

        Follower = self.env['activitypub.follower'].sudo()
        vals = {
            'actor_id': local.id,
            'follower_uri': remote.uri,
            'inbox_url': remote.inbox_url,
            'shared_inbox_url': remote.shared_inbox_url,
            'follow_activity_uri': raw.get('id'),
            'state': 'accepted',
        }
        follower = Follower.search([
            ('actor_id', '=', local.id), ('follower_uri', '=', remote.uri)], limit=1)
        if follower:
            follower.write(vals)
        else:
            follower = Follower.create(vals)

        self._record_inbound(raw, remote, local, state='processed')

        base = local._base_url()
        accept = self.sudo().create({
            'activity_type': 'Accept',
            'direction': 'out',
            'actor_id': local.id,
            'object_uri': raw.get('id'),
            'uri': f'urn:uuid:{uuid.uuid4()}',
            'state': 'pending',
        })
        accept.uri = f'{base}/ap/activities/{accept.id}'
        accept.payload = build_accept(local.actor_url, raw, activity_id=accept.uri)
        accept._queue_deliveries([follower._target_inbox()])
        return 202

    def _ingest_undo(self, raw, remote, target_actor):
        inner = raw.get('object')
        inner_type = inner.get('type') if isinstance(inner, dict) else None
        if inner_type == 'Follow':
            target_uri = self._object_uri(inner.get('object'))
            local = (self.env['activitypub.actor'].sudo()._for_url(target_uri)
                     or target_actor)
            if local:
                self.env['activitypub.follower'].sudo().search([
                    ('actor_id', '=', local.id),
                    ('follower_uri', '=', remote.uri),
                ]).unlink()
            self._record_inbound(raw, remote, local, state='processed')
            return 202
        # Undo of a Like / Announce is Phase 3.
        self._record_inbound(raw, remote, target_actor, state='ignored')
        return 202

    def _ingest_accept(self, raw, remote, target_actor):
        # We do not initiate Follows in this phase; just record it.
        self._record_inbound(raw, remote, target_actor, state='ignored')
        return 202
