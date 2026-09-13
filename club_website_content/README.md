# Club Website Content

Recreates the static content and navigation menu of the club's old
WordPress site ([sonomacountyradioamateurs.com](https://sonomacountyradioamateurs.com/wp/))
as Odoo `website.page` records, scraped and cleaned 2026-09-13.

## What's here

30 pages across 5 sections (Our Club, Repeaters, Events, Resources,
Donate), matching the original site's navigation structure, plus a
`website.menu` hierarchy wiring them into the site's nav bar.

## What's deliberately *not* here

- **The WordPress site's transactional pages** (membership renewal,
  event payment, the auction checkout - everything under Store/ and
  Member Area/). These aren't content to import - they're application
  logic. The right Odoo equivalent is `club_membership`'s dues product
  plus `website_sale` and a real payment provider, not a page import.
- **The forum** (bbPress, 3 categories, 121 topics, ~228 replies) - a
  separate module targeting `website_forum` (confirmed in Odoo 19 CE),
  since it's a different data shape entirely from static pages.
- **Time-bound event details** - specific dates/schedules for Field
  Day, Winter Field Day, VE testing sessions, and public-service events
  are called out in each page's body but not carried over as static
  text. Those belong in Odoo's own Events app, re-entered fresh each
  time, not baked into a page.
- **Linked files** - newsletter PDFs (~90+ across 2019-2026), insurance
  policies, net scripts, and DMR code plugs are all still linked back
  to the original WordPress site's media URLs. Re-hosting them as Odoo
  attachments is a good follow-up, not done in this pass.
- **Images** - the scrape was text-focused; no photos (club logo, Field
  Day photos, repeater sites) were pulled. A separate pass against the
  WP media library would be needed if those are wanted.

## Design choice

Every page is plain, unstyled semantic HTML (headings, paragraphs,
lists) - deliberately basic so it renders correctly on install, then is
easy to restyle with the website builder's own snippets afterward.
Nothing here guesses at visual design.

## Setup

Just install - `website` is the only dependency. All pages are
published on install; no further configuration needed. The nav menu
items are added to whatever site already exists as the default
website (`website.main_menu`) - if there's ever more than one website
in the database, double check the menus landed under the right one.
