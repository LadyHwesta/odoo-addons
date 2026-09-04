# -*- coding: utf-8 -*-
import re

from markupsafe import Markup

from odoo import fields, models

from odoo.addons.activitypub.models.activitypub_service import (
    AS_PUBLIC,
    to_ap_datetime,
)

# Writing any of these on a published post re-federates it.
_TRIGGER_FIELDS = frozenset({
    'name', 'subtitle', 'content', 'teaser_manual', 'website_published',
    'active', 'post_date', 'published_date', 'tag_ids', 'blog_id',
    'author_id', 'cover_properties',
})


class BlogPost(models.Model):
    _name = 'blog.post'
    _inherit = ['blog.post', 'activitypub.federatable']

    def _ap_trigger_fields(self):
        return _TRIGGER_FIELDS

    def _ap_object_type(self):
        # Mastodon's Create handler only materializes a visible status for
        # `Note` (and `Question` for polls); `Article` is accepted and
        # counted but never rendered in the timeline / profile posts tab on
        # stock Mastodon - confirmed against a real instance. `Note` is the
        # object type every mainstream server actually displays.
        return 'Note'

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
        url = base + path
        published = self.post_date or self.published_date or self.create_date

        # `self.content` is raw website-builder HTML - snippet divs,
        # data-oe-* attributes, layout classes - never meant to be embedded
        # in a microblog post; every remote server's sanitizer treats it
        # differently and none of them render it usefully. `teaser` is
        # Odoo's own plain-text, HTML-stripped ~200-char excerpt of it
        # (website_blog's own list-view summary), which is exactly the
        # shape every Fediverse client expects. A Note has no separate
        # title either, so the title (linked to the post) leads the body;
        # `summary` is never set - on an AS object Mastodon reads that as a
        # *content warning* and hides the post behind "Show more".
        heading = Markup('<p><strong><a href="%s">%s</a></strong></p>') % (
            url, self.name or '')
        body = str(heading)
        if self.subtitle:
            body += str(Markup('<p><em>%s</em></p>') % self.subtitle)
        if self.teaser:
            body += str(Markup('<p>%s</p>') % self.teaser)
        body += str(Markup('<p><a href="%s">Continue reading&#8230;</a></p>') % url)

        note = {
            'name': self.name or '',
            'content': body,
            'mediaType': 'text/html',
            'url': url,
            'attributedTo': actor.actor_url,
            'to': [AS_PUBLIC],
            'cc': [actor._endpoint('/followers')],
            'published': to_ap_datetime(published),
        }
        tags = [
            {'type': 'Hashtag', 'name': '#' + re.sub(r'\s+', '', tag.name)}
            for tag in self.tag_ids if tag.name
        ]
        if tags:
            note['tag'] = tags
        cover = self._ap_cover_image_url(base)
        if cover:
            note['attachment'] = [{'type': 'Image', 'url': cover}]
        return note
