# ActivityPub – Website Blog

Federates `website_blog` posts to the Fediverse as ActivityStreams `Note`
objects, on top of the [`activitypub`](../activitypub) engine.

> **Why `Note`, not `Article`?** Confirmed against a real Mastodon instance:
> `Article` is accepted and even counted towards the profile's post count,
> but Mastodon's `Create` handler never materializes a visible status for
> it - the post silently never appears in the timeline or the Posts tab.
> `Note` is the type every mainstream server actually renders.

## What it does

- Adds **Federate posts as** (`activitypub_actor_id`) to the blog form
  (`blog.blog`). When set, the lifecycle of a post in that blog drives
  federation:

  | Post change | Sent to followers |
  |---|---|
  | becomes public (published, active, `post_date` reached) | `Create` (Note) |
  | edited while public (title, body, subtitle, tags, …) | `Update` |
  | unpublished, archived, or deleted | `Delete` (Tombstone) |

- **Author actors take precedence.** If the post's author is an Odoo user
  who has their own `activitypub.actor` on the same website, the Note is
  `attributedTo` that author and delivered to *their* followers instead of
  the blog's. One post has exactly one `attributedTo`.

- Posts that are not public never federate; making one public later
  publishes it then. Re-publishing an unpublished post sends a fresh
  `Create` under a **brand new object URI** - never the one already
  tombstoned by the earlier `Delete`. Reusing a deleted URI is exactly what
  broke this in testing: Mastodon's own `Create` handler permanently
  refuses to resurrect a URI it already has a Tombstone for, so a
  republished post silently never appeared even though delivery itself
  succeeded with no error.

A `Note` has no separate title Mastodon displays, so the body is built as:
the post title (linked back to the page), the subtitle, Odoo's own
`teaser` (a plain-text, HTML-stripped ~200-char excerpt - the same one
`website_blog`'s own list view uses), and a "Continue reading" link.
**The raw `content` field is never embedded** - it's website-builder
markup (snippet divs, `data-oe-*`/`data-snippet` attributes, layout
classes), not something any Fediverse client's sanitizer renders
sensibly; a real Mastodon post showed it as literal, unrendered angle
brackets. **`summary` is also deliberately never set** - on an
ActivityStreams object it is read as a *content warning* by Mastodon,
which would hide the post behind a "Show more" click. The Note also
carries the absolute `url` of the blog post, `published`, the blog tags as
`Hashtag`s, and the cover image as an `attachment`.

## Setup

1. Install this module (pulls in `activitypub` and `website_blog`).
2. Create an `activitypub.actor` (Fediverse → Actors) on the right website —
   e.g. a `Group` actor `@blog@yourdomain`.
3. On the blog (Website → Blog → Blogs), set **Federate posts as** to it.
4. Publish a post. Within a minute the delivery cron signs and POSTs a
   `Create` to every follower's inbox; check **Fediverse → Delivery Queue**
   for status.

## Testing status

`tests/test_blog_federation.py` (`TransactionCase`): publishing creates a
`Note` object + `Create` activity `attributedTo` the actor and addressed to
Public, with the title linked in the body and no `summary` key, and queues
one delivery per follower; the body carries the plain-text teaser and a
"Continue reading" link, with none of the raw builder markup (snippet
divs, `data-snippet` attributes) leaking through; editing a published post
sends `Update` with the new content; unpublishing and deleting send
`Delete` and tombstone the object; a non-public post or a blog with no
actor federates nothing; an author with their own actor overrides the blog
actor; unpublishing then republishing gets a brand new object/URI, never
the one already tombstoned.

**Verified end to end against a real Mastodon instance.** Getting there
took two fixes beyond the `Note` switch above: the raw-`content` /
website-builder-markup issue (see above), and a subtler one - reusing the
same object URI across an unpublish → republish cycle. Once a `Delete` for
a URI has gone out, Mastodon (correctly, per its own source) permanently
refuses to ever create a status for that URI again, silently and without
error; the engine now mints a brand new object URI for every `Create`
that follows a `Delete`, which is what actually made a republished post
show up. `GET /api/v1/accounts/<id>/statuses` on the Mastodon side is the
way to confirm a post genuinely landed - the account/profile page's post
count can be wrong (see the engine README for why) or just slow to
update, in a way that reading the actual statuses list isn't.

## Files

- `models/blog_blog.py` — the `activitypub_actor_id` field.
- `models/blog_post.py` — inherits `activitypub.federatable` and implements
  its four hooks: actor resolution (`_ap_actor`), publicness
  (`_ap_is_public`), the type (`Note`), and the object builder
  (`_ap_build_object`). Lifecycle plumbing lives in the mixin.
