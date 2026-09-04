# -*- coding: utf-8 -*-
{
    'name': 'ActivityPub / Fediverse Federation',
    'version': '19.0.1.3.0',
    'category': 'Website',
    'summary': 'Federate this Odoo instance into the Fediverse (Mastodon, '
               'Pleroma, Misskey, ...) over ActivityPub',
    'description': """
ActivityPub / Fediverse Federation
==================================

The federation engine. On its own it publishes no Odoo content - it
provides the plumbing that the ``activitypub_website_blog`` and
``activitypub_website_event`` bridge modules build on:

* **Actors** - a federated identity scoped to a website. Each gets its own
  RSA key pair, generated on creation, whose private half never leaves the
  server.
* **Discovery** - WebFinger (``/.well-known/webfinger``) and NodeInfo, so a
  handle like ``@news@example.com`` resolves from a Mastodon search box.
* **The Actor endpoint** - ``/ap/actors/<id>`` served as ActivityStreams
  JSON-LD to Fediverse servers and redirected to the website for browsers.
* **HTTP Signatures** (draft-cavage-12) - the request signing / verification
  every mainstream server requires for server-to-server traffic.
* **Outbound delivery** - a signed, retrying delivery queue that fans an
  activity out to every follower's inbox.
* **Inbox** - verifies the sender's signature, then handles Follow / Undo /
  Accept, inbound replies (optionally to chatter), edits, deletes, and
  Like / Announce reactions. SSRF-guarded, body-capped, rate-limited.
* **``activitypub.federatable``** - the mixin bridges use to turn a content
  record into a federated object.

Multi-website aware: an actor's ``@user@domain`` host comes from its
website's *Website Domain*, so each company branch federates under its own
domain.

No extra Python packages: only ``requests`` and ``cryptography``, both
already bundled with Odoo.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'images': ['static/description/banner.png'],
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['website', 'mail'],
    'external_dependencies': {
        'python': ['requests', 'cryptography'],
    },
    'data': [
        'security/activitypub_security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/activitypub_actor_views.xml',
        'views/activitypub_activity_views.xml',
        'views/activitypub_menus.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': True,
}
