# Club Forum Content

Recreates the club's old WordPress forum (bbPress plugin, at
[sonomacountyradioamateurs.com/wp/forums/](https://sonomacountyradioamateurs.com/wp/forums/))
as Odoo `website_forum` data, scraped and cleaned 2026-09-13.

## What's here

3 real forum categories, matched to the live site's own listing -
**Activities**, **Announcements and News**, **Technical Questions and
Answers** - and 110 topics (243 posts total: 110 questions + 133
replies) ported from the site's 128-topic sitemap. (A 4th forum,
"Help", shows up on a fresh `website_forum` install - that's the
module's own default forum, not something this one creates.)

18 of the 128 sitemap slugs 404 on the live site (mostly older
Sales/Swaps-style posts, presumably removed once the item sold) and
were skipped rather than guessed at.

## Attribution

Every historical post is attributed to a single inactive "Forum
Archive Import" system user (`forum-archive-import`), rather than
creating ~80+ individual accounts for every original poster. Each
post's body is prefixed with a plain-text line naming the real
original author and posting date, so that information isn't lost - it
just isn't a clickable profile link the way a real Odoo user's post
would be. If a poster turns out to already be a current member with
their own Odoo login, re-attributing their specific posts by hand
afterward is possible but wasn't done automatically here.

Original post/reply timestamps *are* preserved on `create_date`
(Odoo's field-loading code allows a data record to set it explicitly
during module installation), so the forum reads in its real
chronological order - spanning 2014 through 2026 - rather than
everything showing today's date. Times were converted from the
site's displayed Pacific time to UTC; day-level accuracy was
prioritized over the exact hour for older/terser posts.

## What's deliberately *not* here

- **A handful of ambiguous cases weren't force-fit into a 4th
  category.** One early topic's page reported `CATEGORY: Public
  Service`, which isn't one of the site's 3 real subforums - judged to
  be the scrape picking up the *website's* Public Service section
  rather than an actual subforum, and filed under Activities instead
  (fits the content - a volunteer sign-up post - anyway).
- **Linked attachments** (PDFs, photos) referenced in several posts
  still point at the original WordPress site's media URLs. Re-hosting
  them as Odoo attachments is a good follow-up, not done in this pass.
- **Individual poster accounts** - see Attribution above.

## Setup

Just install - `website_forum` is the only dependency. All posts are
loaded with `noupdate="1"`, so re-running `-u` on this module won't
reset anything a moderator has since edited, or wipe out real replies
members have posted since installing it.
