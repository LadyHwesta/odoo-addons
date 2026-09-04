# -*- coding: utf-8 -*-
from odoo import fields, models


class BlogBlog(models.Model):
    _inherit = 'blog.blog'

    activitypub_actor_id = fields.Many2one(
        'activitypub.actor', string='Federate posts as',
        domain="[('website_id', '=', website_id)]",
        help='When set, posts published in this blog are announced to this '
             "actor's Fediverse followers - unless the post's author has their "
             'own actor on the same website, which then takes precedence.')
