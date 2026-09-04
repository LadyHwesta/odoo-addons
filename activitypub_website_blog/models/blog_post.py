# -*- coding: utf-8 -*-
import logging
import re

from odoo import api, fields, models

from odoo.addons.activitypub.models.activitypub_service import (
    AS_PUBLIC,
    to_ap_datetime,
)

_logger = logging.getLogger(__name__)

# Writing any of these on a published post is a reason to re-federate it.
_FEDERATION_TRIGGER_FIELDS = frozenset({
    'name', 'subtitle', 'content', 'website_published', 'active',
    'post_date', 'published_date', 'tag_ids', 'blog_id', 'author_id',
})


class BlogPost(models.Model):
    _inherit = 'blog.post'

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------
    def _ap_actor(self):
        """The actor a post federates through: the author's own actor on the
        post's website if they have one, otherwise the blog's actor. Empty
        recordset when neither exists."""
        self.ensure_one()
        Actor = self.env['activitypub.actor'].sudo()
        blog_actor = self.blog_id.sudo().activitypub_actor_id
        website = (self.website_id or blog_actor.website_id
                   or self.env['website'].search([], limit=1))
        user = self.author_id.user_ids[:1]
        if user and website:
            author_actor = Actor.search([
                ('user_id', '=', user.id),
                ('website_id', '=', website.id),
                ('active', '=', True),
            ], limit=1)
            if author_actor:
                return author_actor
        return blog_actor if blog_actor.active else Actor.browse()

    def _ap_is_public(self):
        self.ensure_one()
        now = fields.Datetime.now()
        return bool(
            self.website_published and self.active
            and (not self.post_date or self.post_date <= now))

    # ------------------------------------------------------------------
    # Article rendering
    # ------------------------------------------------------------------
    def _ap_build_article(self, actor):
        self.ensure_one()
        base = actor._base_url()
        path = self.website_url or ('/blog/%s/%s' % (self.blog_id.id, self.id))
        tags = [
            {'type': 'Hashtag', 'name': '#' + re.sub(r'\s+', '', tag.name)}
            for tag in self.tag_ids if tag.name
        ]
        published = self.post_date or self.published_date or self.create_date
        article = {
            'name': self.name or '',
            'content': self.content or '',
            'mediaType': 'text/html',
            'url': base + path,
            'attributedTo': actor.actor_url,
            'to': [AS_PUBLIC],
            'cc': [actor._endpoint('/followers')],
            'published': to_ap_datetime(published),
        }
        if self.subtitle:
            article['summary'] = self.subtitle
        if tags:
            article['tag'] = tags
        return article

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------
    def _ap_sync(self, retract=False):
        if self.env.context.get('activitypub_no_sync'):
            return
        Object = self.env['activitypub.object'].sudo()
        for post in self:
            existing = Object.search([
                ('source_model', '=', 'blog.post'),
                ('source_res_id', '=', post.id),
            ], limit=1)
            live = existing and not existing.deleted
            actor = post._ap_actor()
            should_publish = (not retract) and post._ap_is_public() and bool(actor)

            if not should_publish:
                if live and existing.actor_id:
                    existing.actor_id._ap_retract('blog.post', post.id)
                continue

            # Attribution moved to a different actor: retract from the old one
            # and start fresh on the new.
            if live and existing.actor_id and existing.actor_id != actor:
                existing.actor_id._ap_retract('blog.post', post.id)
                live = False

            activity_type = 'Update' if live else 'Create'
            actor._ap_publish('blog.post', post.id, 'Article',
                              post._ap_build_article(actor),
                              activity_type=activity_type)

    # ------------------------------------------------------------------
    # ORM hooks
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        posts = super().create(vals_list)
        posts._ap_sync()
        return posts

    def write(self, vals):
        res = super().write(vals)
        if _FEDERATION_TRIGGER_FIELDS.intersection(vals):
            self._ap_sync()
        return res

    def unlink(self):
        # Retract while the records (and their ids) still exist.
        self._ap_sync(retract=True)
        return super().unlink()
