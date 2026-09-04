# ActivityPub – Website Blog

Federates `website_blog` posts to the Fediverse as ActivityStreams
`Article` objects, on top of the [`activitypub`](../activitypub) engine.

## What it does

- Adds **Federate posts as** (`activitypub_actor_id`) to the blog form
  (`blog.blog`). When set, the lifecycle of a post in that blog drives
  federation:

  | Post change | Sent to followers |
  |---|---|
  | becomes public (published, active, `post_date` reached) | `Create` (Article) |
  | edited while public (title, body, subtitle, tags, …) | `Update` |
  | unpublished, archived, or deleted | `Delete` (Tombstone) |

- **Author actors take precedence.** If the post's author is an Odoo user
  who has their own `activitypub.actor` on the same website, the Article is
  `attributedTo` that author and delivered to *their* followers instead of
  the blog's. One post has exactly one `attributedTo`.

- Posts that are not public never federate; making one public later
  publishes it then. Re-publishing an unpublished post sends a fresh
  `Create` (reusing the original object URI).

The Article carries `name`, sanitized `content` (`mediaType: text/html`),
the absolute `url` of the blog post, `published`, the blog tags as
`Hashtag`s, and `summary` from the post subtitle. Cover images / other
attachments are Phase 4.

## Setup

1. Install this module (pulls in `activitypub` and `website_blog`).
2. Create an `activitypub.actor` (Fediverse → Actors) on the right website —
   e.g. a `Group` actor `@blog@yourdomain`.
3. On the blog (Website → Blog → Blogs), set **Federate posts as** to it.
4. Publish a post. Within a minute the delivery cron signs and POSTs a
   `Create` to every follower's inbox; check **Fediverse → Delivery Queue**
   for status.

## Testing status

`tests/test_blog_federation.py` (`TransactionCase`): publishing creates an
Article object + `Create` activity `attributedTo` the actor and addressed
to Public, and queues one delivery per follower; editing a published post
sends `Update` with the new content; unpublishing and deleting send
`Delete` and tombstone the object; a non-public post or a blog with no
actor federates nothing; an author with their own actor overrides the blog
actor. Not yet run against a real Mastodon instance — Phase 4.

## Files

- `models/blog_blog.py` — the `activitypub_actor_id` field.
- `models/blog_post.py` — actor resolution (`_ap_actor`), the Article
  builder (`_ap_build_article`), and the create / write / unlink hooks that
  call the engine's `_ap_publish` / `_ap_retract`.
