# -*- coding: utf-8 -*-
import base64
import binascii
import logging
import re
import uuid
from urllib.parse import urlparse

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.mimetypes import guess_mimetype

from .activitypub_service import (
    AS_PUBLIC,
    USERNAME_RE,
    build_actor_document,
    build_create,
    build_delete,
    build_update,
    generate_rsa_keypair,
)

_ACTOR_URL_RE = re.compile(r'/ap/actors/(\d+)/?$')

_logger = logging.getLogger(__name__)

ACTOR_TYPES = [
    ('Service', 'Service - the website itself'),
    ('Person', 'Person - an individual author'),
    ('Group', 'Group - a feed people follow'),
    ('Organization', 'Organization'),
]


class ActivityPubActor(models.Model):
    """A federated identity. Every actor is scoped to a website, whose public
    *Website Domain* becomes the host part of the ``@user@domain`` handle -
    so each company branch federates under its own domain from one Odoo
    instance. An RSA key pair is generated on creation; the private half is
    readable only by the system group and never leaves the server.
    """
    _name = 'activitypub.actor'
    _description = 'ActivityPub Actor'
    _order = 'website_id, username'

    active = fields.Boolean(default=True)
    website_id = fields.Many2one(
        'website', string='Website', required=True, ondelete='cascade', index=True,
        default=lambda self: self.env['website'].search([], limit=1),
        help='The website this actor belongs to. Its Website Domain becomes '
             'the "@user@domain" host, so that domain must be set (and serve '
             'this Odoo over HTTPS) for federation to work.')
    actor_type = fields.Selection(
        ACTOR_TYPES, string='Type', required=True, default='Service')
    username = fields.Char(
        required=True,
        help='Local part of the Fediverse handle: @<username>@<domain>. '
             '1-64 lowercase letters, digits, "_" or "-". Once anything has '
             'been published under this actor the username is locked, because '
             'remote servers have followed it by that name.')
    name = fields.Char(required=True, help='Human-readable name shown on the '
                       'Fediverse profile (the ActivityStreams "name").')
    summary = fields.Html(string='Bio', sanitize=True)
    icon = fields.Image(string='Avatar', max_width=400, max_height=400)

    user_id = fields.Many2one(
        'res.users', string='Odoo User', ondelete='set null', index=True,
        help='Optional. If set, this is that user\'s personal actor.')

    federated_once = fields.Boolean(
        string='Has Federated', default=False, copy=False, readonly=True,
        help='Set the first time something is published under this actor. '
             'While true, the username cannot be changed.')

    public_key_pem = fields.Text(string='Public Key', readonly=True, copy=False)
    private_key_pem = fields.Text(
        string='Private Key', readonly=True, copy=False, groups='base.group_system',
        help='RSA private key used to sign this actor\'s outbound federated '
             'requests. Never served to anyone.')

    handle = fields.Char(compute='_compute_urls')
    domain = fields.Char(compute='_compute_urls',
                         help='Host part of the handle, taken from the website domain.')
    actor_url = fields.Char(compute='_compute_urls', string='Actor URL')
    key_id = fields.Char(compute='_compute_urls', string='Key ID')

    follower_ids = fields.One2many(
        'activitypub.follower', 'actor_id', string='Followers')
    follower_count = fields.Integer(compute='_compute_follower_count')

    _username_website_uniq = models.Constraint(
        'unique(username, website_id)',
        'That username is already taken on this website.',
    )

    # ------------------------------------------------------------------
    # Computed URLs
    # ------------------------------------------------------------------
    @api.depends('username', 'website_id', 'website_id.domain')
    def _compute_urls(self):
        fallback = (self.env['ir.config_parameter'].sudo()
                    .get_param('web.base.url') or '').rstrip('/')
        for actor in self:
            base = (actor.website_id.domain or '').strip().rstrip('/') or fallback
            host = urlparse(base).hostname or ''
            actor.domain = host
            actor.handle = (f'@{actor.username}@{host}'
                            if actor.username and host else False)
            actor.actor_url = (f'{base}/ap/actors/{actor.id}'
                               if actor.id and base else False)
            actor.key_id = f'{actor.actor_url}#main-key' if actor.actor_url else False

    def _compute_follower_count(self):
        grouped = self.env['activitypub.follower']._read_group(
            [('actor_id', 'in', self.ids), ('state', '=', 'accepted')],
            ['actor_id'], ['__count'])
        counts = {actor.id: count for actor, count in grouped}
        for actor in self:
            actor.follower_count = counts.get(actor.id, 0)

    def _base_url(self):
        self.ensure_one()
        fallback = (self.env['ir.config_parameter'].sudo()
                    .get_param('web.base.url') or '').rstrip('/')
        return (self.website_id.domain or '').strip().rstrip('/') or fallback

    def _endpoint(self, suffix=''):
        self.ensure_one()
        return f'{self._base_url()}/ap/actors/{self.id}{suffix}'

    def _shared_inbox_url(self):
        self.ensure_one()
        return f'{self._base_url()}/ap/inbox'

    def _human_url(self):
        """Where a browser (rather than a Fediverse server) should be sent."""
        self.ensure_one()
        return self._base_url() or '/'

    def _icon_bytes(self):
        """Raw avatar bytes, or ``None``. Served by the public
        ``/ap/actors/<id>/icon`` route (``/web/image`` needs the caller to
        have model access, which a Fediverse server does not)."""
        self.ensure_one()
        if not self.icon:
            return None
        try:
            return base64.b64decode(self.icon)
        except (binascii.Error, ValueError):
            return None

    def _icon_info(self):
        self.ensure_one()
        data = self._icon_bytes()
        if not data:
            return None
        return {
            'url': f'{self._base_url()}/ap/actors/{self.id}/icon',
            'mediaType': guess_mimetype(data, default='image/png'),
        }

    def _ap_actor_document(self):
        """The ActivityStreams Actor object served at ``actor_url``."""
        self.ensure_one()
        return build_actor_document(
            actor_url=self.actor_url,
            username=self.username,
            name=self.name or self.username,
            actor_type=self.actor_type,
            public_pem=self.public_key_pem or '',
            inbox_url=self._endpoint('/inbox'),
            outbox_url=self._endpoint('/outbox'),
            followers_url=self._endpoint('/followers'),
            following_url=self._endpoint('/following'),
            shared_inbox_url=self._shared_inbox_url(),
            summary_html=self.summary or None,
            icon=self._icon_info(),
            published=self.create_date,
        )

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('username')
    def _check_username(self):
        for actor in self:
            if not actor.username or not USERNAME_RE.match(actor.username):
                raise ValidationError(_(
                    'Username "%s" is not valid: use 1-64 lowercase letters, '
                    'digits, "_" or "-".', actor.username or ''))

    @api.constrains('icon')
    def _check_icon_not_svg(self):
        for actor in self:
            data = actor._icon_bytes()
            if data and guess_mimetype(data, default='') == 'image/svg+xml':
                raise ValidationError(_(
                    'Fediverse servers reject SVG avatars for security '
                    'reasons - they would just show a placeholder. Upload a '
                    'PNG or JPEG image instead.'))

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('username'):
                vals['username'] = vals['username'].strip().lower()
            if not vals.get('name') and vals.get('username'):
                vals['name'] = vals['username']
        actors = super().create(vals_list)
        # Key generation is done in a second pass under sudo: the private key
        # field is system-only, so a Fediverse Manager (who is not a system
        # user) could not set it inline in the create vals.
        for actor in actors.sudo():
            if not actor.private_key_pem:
                private_pem, public_pem = generate_rsa_keypair()
                actor.write({
                    'private_key_pem': private_pem,
                    'public_key_pem': public_pem,
                })
        return actors

    def write(self, vals):
        if 'username' in vals and vals['username']:
            vals['username'] = vals['username'].strip().lower()
            locked = self.filtered('federated_once')
            if locked and any(a.username != vals['username'] for a in locked):
                raise ValidationError(_(
                    'The username of an actor that has already federated '
                    'cannot be changed: remote servers have followed it by '
                    'that name. Create a new actor instead.'))
        return super().write(vals)

    # ------------------------------------------------------------------
    # Lookup + delivery targets
    # ------------------------------------------------------------------
    @api.model
    def _for_url(self, url):
        """Resolve one of our actor URLs (``.../ap/actors/<id>``) back to its
        record. Matches on the id segment; returns an empty recordset when the
        URL is not ours."""
        match = _ACTOR_URL_RE.search(url or '')
        if not match:
            return self.browse()
        return self.browse(int(match.group(1))).exists()

    def _follower_inboxes(self):
        """Distinct set of inbox URLs to deliver to - the shared inbox when a
        follower advertises one, so several followers on the same server
        collapse to a single POST."""
        self.ensure_one()
        return {
            f._target_inbox()
            for f in self.follower_ids
            if f.state == 'accepted' and f._target_inbox()
        }

    # ------------------------------------------------------------------
    # Outbound publishing
    # ------------------------------------------------------------------
    def _ap_publish(self, source_model, source_res_id, object_type, ap_object,
                    activity_type='Create'):
        """Store / refresh the local object for ``(source_model, source_res_id)``,
        wrap it in a ``Create`` or ``Update`` activity, and queue delivery to
        every follower. Returns the ``activitypub.activity`` record."""
        self.ensure_one()
        Object = self.env['activitypub.object'].sudo()
        Activity = self.env['activitypub.activity'].sudo()
        base = self._base_url()

        # A previously-deleted object is excluded here on purpose: once a
        # Delete/Tombstone has gone out for a URI, compliant servers (e.g.
        # Mastodon) permanently refuse to resurrect a new Create for that
        # same id - confirmed against Mastodon's own source, which rejects
        # a Create outright if a Tombstone already exists for the object
        # URI. Re-publishing after a retract must mint a fresh URI instead
        # of reusing the now-poisoned one; the old row stays as history.
        obj = Object.search([
            ('source_model', '=', source_model),
            ('source_res_id', '=', source_res_id),
            ('deleted', '=', False),
        ], limit=1)
        if not obj:
            obj = Object.create({
                'local': True,
                'actor_id': self.id,
                'object_type': object_type,
                'source_model': source_model,
                'source_res_id': source_res_id,
                'uri': f'urn:uuid:{uuid.uuid4()}',
            })
            obj.uri = f'{base}/ap/objects/{obj.id}'

        payload = dict(ap_object)
        payload['id'] = obj.uri
        payload['type'] = object_type
        payload.setdefault('attributedTo', self.actor_url)
        payload.setdefault('to', [AS_PUBLIC])
        payload.setdefault('cc', [self._endpoint('/followers')])
        obj.write({
            'object_type': object_type,
            'payload': payload,
            'deleted': False,
            'published': obj.published or fields.Datetime.now(),
        })

        activity = Activity.create({
            'activity_type': activity_type,
            'direction': 'out',
            'actor_id': self.id,
            'object_id': obj.id,
            'uri': f'urn:uuid:{uuid.uuid4()}',
            'state': 'pending',
        })
        activity.uri = f'{base}/ap/activities/{activity.id}'
        builder = build_update if activity_type == 'Update' else build_create
        activity.payload = builder(
            self.actor_url, payload, activity_id=activity.uri,
            to=payload['to'], cc=payload['cc'],
            published=payload.get('published'))
        activity._queue_deliveries(self._follower_inboxes())

        if not self.federated_once:
            self.sudo().federated_once = True
        return activity

    def _ap_retract(self, source_model, source_res_id):
        """Emit a ``Delete`` for a previously published local object and mark
        it deleted. No-op when nothing was published."""
        self.ensure_one()
        obj = self.env['activitypub.object'].sudo().search([
            ('source_model', '=', source_model),
            ('source_res_id', '=', source_res_id),
            ('deleted', '=', False),
        ], limit=1)
        if not obj:
            return self.env['activitypub.activity']
        base = self._base_url()
        activity = self.env['activitypub.activity'].sudo().create({
            'activity_type': 'Delete',
            'direction': 'out',
            'actor_id': self.id,
            'object_id': obj.id,
            'uri': f'urn:uuid:{uuid.uuid4()}',
            'state': 'pending',
        })
        activity.uri = f'{base}/ap/activities/{activity.id}'
        activity.payload = build_delete(
            self.actor_url, obj.uri, activity_id=activity.uri,
            cc=[self._endpoint('/followers')])
        obj.deleted = True
        activity._queue_deliveries(self._follower_inboxes())
        return activity

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_regenerate_keys(self):
        """Replace the key pair. This invalidates every existing follow, since
        remote servers have cached the old public key - use only for recovery."""
        for actor in self:
            private_pem, public_pem = generate_rsa_keypair()
            actor.sudo().write({
                'private_key_pem': private_pem,
                'public_key_pem': public_pem,
            })
        return True

    def action_view_followers(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Followers'),
            'res_model': 'activitypub.follower',
            'view_mode': 'list,form',
            'domain': [('actor_id', '=', self.id)],
            'context': {'default_actor_id': self.id},
        }

    def action_push_profile(self):
        """Send an ``Update`` so followers refresh their cached copy of this
        actor - name, bio and, in particular, the avatar. Remote servers only
        re-fetch a profile on their own schedule (~a day) otherwise, so run
        this after changing the avatar or bio."""
        Activity = self.env['activitypub.activity'].sudo()
        for actor in self:
            inboxes = actor._follower_inboxes()
            if not inboxes:
                continue
            base = actor._base_url()
            activity = Activity.create({
                'activity_type': 'Update',
                'direction': 'out',
                'actor_id': actor.id,
                'uri': f'urn:uuid:{uuid.uuid4()}',
                'state': 'pending',
            })
            activity.uri = f'{base}/ap/activities/{activity.id}'
            activity.payload = build_update(
                actor.actor_url, actor._ap_actor_document(),
                activity_id=activity.uri, to=[AS_PUBLIC],
                cc=[actor._endpoint('/followers')])
            activity._queue_deliveries(inboxes)
        return True
