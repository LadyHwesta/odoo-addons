# -*- coding: utf-8 -*-
import logging
from urllib.parse import urlparse

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .activitypub_service import (
    USERNAME_RE,
    build_actor_document,
    generate_rsa_keypair,
)

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
    _rec_name = 'display_name'
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
    display_name = fields.Char(required=True)
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

    def _icon_url(self):
        self.ensure_one()
        if not self.icon:
            return None
        return f'{self._base_url()}/web/image/activitypub.actor/{self.id}/icon'

    def _ap_actor_document(self):
        """The ActivityStreams Actor object served at ``actor_url``."""
        self.ensure_one()
        return build_actor_document(
            actor_url=self.actor_url,
            username=self.username,
            name=self.display_name or self.username,
            actor_type=self.actor_type,
            public_pem=self.public_key_pem or '',
            inbox_url=self._endpoint('/inbox'),
            outbox_url=self._endpoint('/outbox'),
            followers_url=self._endpoint('/followers'),
            following_url=self._endpoint('/following'),
            shared_inbox_url=self._shared_inbox_url(),
            summary_html=self.summary or None,
            icon_url=self._icon_url(),
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

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('username'):
                vals['username'] = vals['username'].strip().lower()
            if not vals.get('display_name') and vals.get('username'):
                vals['display_name'] = vals['username']
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
