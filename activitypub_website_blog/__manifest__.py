# -*- coding: utf-8 -*-
{
    'name': 'ActivityPub - Website Blog',
    'version': '19.0.1.0.0',
    'category': 'Website/Blog',
    'summary': 'Federate published blog posts to the Fediverse as Articles',
    'description': """
ActivityPub bridge for Website Blog
===================================

Publishes ``blog.post`` records to the Fediverse as ActivityStreams
``Article`` objects, using the ``activitypub`` engine.

* A blog gets a **Federate posts as** actor (``blog.blog`` form). When set,
  publishing a post in that blog sends a ``Create`` to the actor's
  followers; editing a published post sends an ``Update``; unpublishing or
  deleting it sends a ``Delete``.
* If the post's author has their **own** actor (an ``activitypub.actor``
  with that user set) on the same website, the post is attributed to the
  author instead of the blog - one post, one ``attributedTo``, delivered to
  that actor's followers.
* Posts that are not public (unpublished, archived, or future-dated) do not
  federate; making one public later publishes it then.

Install ``activitypub`` first and configure at least one actor.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['activitypub', 'website_blog'],
    'data': [
        'views/blog_views.xml',
    ],
    'installable': True,
    'application': False,
}
