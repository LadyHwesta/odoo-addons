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

## Images

19 content photos/logos were re-fetched from the original site's media
library and are bundled directly in the module, under
`static/src/img/`, referenced with plain `<img>` tags in the pages
that used them - the DMR Association logo, Yaesu Fusion, Winter Field
Day, and Emergency Services headers; the public-service and FRS/GMRS
radio photos; and three "welcome" photos on the homepage (`/our-club`).
No `ir.attachment` records were created for these - a bundled static
file behaves identically for this purpose (Odoo's website builder can
still replace any of them with a new upload, same as an attachment-backed
image) and is far simpler to review and version in git than binary data
inlined into XML. Say so if literal `ir.attachment` records are wanted
instead, e.g. to manage these specific images through Odoo's own
Attachments/Documents UI going forward.

Not re-hosted: ~13 external event-sponsor logos on the Public Service
page (Climate Ride, Fish Rock, etc. - third-party branding, not the
club's own), and the newsletter/insurance/code-plug PDFs noted above.

## Design choice

Every page is plain, unstyled semantic HTML (headings, paragraphs,
lists) - deliberately basic so it renders correctly on install, then is
easy to restyle with the website builder's own snippets afterward.
Nothing here guesses at visual design.

## Setup

Just install - `website` is the only dependency. All pages are
published on install; the site's homepage is set to `/our-club`; and
the nav menu (5 top-level sections, with dropdowns) is built and
attached to the target website - all handled by a `post_init_hook`
(see `hooks.py`), not by data-file XML. If there's more than one
website in the database, double-check the content landed under the
right one (`hooks.py` picks `website.default_website`, falling back to
whichever website exists if that xmlid is missing).

**If upgrading from a version before 19.0.1.2.0**: that version's
`data/menus.xml` had a real bug - a `website.menu` record created
without an explicit `website_id` gets silently duplicated per website
by Odoo's own `website.menu.create()`, and an *extra* orphan copy ends
up owning the record's external ID whenever its parent is
`website.main_menu`; any child menu referencing that ID as its own
parent then attaches to the orphan instead of the copy that's actually
part of a site's rendered nav tree - so the dropdowns never appeared,
even though the top-level items sometimes did. A migration script
(`migrations/19.0.1.2.0/post-fix-nav-menu.py`) rebuilds the whole menu
correctly on upgrade. It can't safely clean up the *old* top-level
orphans it leaves behind (a core `website.menu.unlink()` override
means deleting one of those can cascade into deleting unrelated
menus on other websites - see the DANGER note in `hooks.py`), so after
upgrading you may see one or two empty, harmless duplicate top-level
entries (e.g. a second "Our Club" with no dropdown) - safe to delete
by hand via the website builder's menu editor if they bother you.
