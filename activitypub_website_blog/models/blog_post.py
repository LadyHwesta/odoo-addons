# -*- coding: utf-8 -*-
import re

from odoo import fields, models

from odoo.addons.activitypub.models.activitypub_service import (
    AS_PUBLIC,
    to_ap_datetime,
)

# Writing any of these on a published post re-federates it.
_TRIGGER_FIELDS = frozenset({
    'name', 'subtitle', 'content', 'website_published', 'active',
    'post_date', 'published_date', 'tag_ids', 'blog_id', 'author_id',
    'cover_properties',
})


class BlogPost(models.Model):
    _name = 'blog.post'
    _inherit = ['blog.post', 'activitypub.federatable']

    def _ap_trigger_fields(self):
        return _TRIGGER_FIELDS

    def _ap_object_type(self):
        return 'Article'

    def _ap_actor(self):
        """The author's own actor on the post's website if they have one,
        otherwise the blog's actor."""
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

    def _ap_build_object(self, actor):
        self.ensure_one()
        base = actor._base_url()
        path = self.website_url or ('/blog/%s/%s' % (self.blog_id.id, self.id))
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
        tags = [
            {'type': 'Hashtag', 'name': '#' + re.sub(r'\s+', '', tag.name)}
            for tag in self.tag_ids if tag.name
        ]
        if tags:
            article['tag'] = tags
        cover = self._ap_cover_image_url(base)
        if cover:
            article['attachment'] = [{'type': 'Image', 'url': cover}]
        return article
