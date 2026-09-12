# Progressive Web App Icon (iOS + Visibility)

Completes [OCA's `web_pwa_customize`](https://github.com/OCA/web/tree/19.0/web_pwa_customize)
(icon, short name, and colors for Odoo's "Install app" prompt) rather
than reimplementing it - that module covers Chrome/Edge/Android but
leaves two things unsolved, which is what this module actually does.

## What was missing

- **iOS Safari never sees any of it.** Safari reads the
  `apple-touch-icon` `<link>` tag, not the PWA manifest, and
  `web_pwa_customize` only ever touches `/web/manifest.webmanifest`.
  Install from an iPhone and you still get Odoo's own stock icon.
- **The settings stay hidden.** Both `web_pwa_customize`'s own fields
  and core's pre-existing `web.web_app_name` (the app's actual *name* -
  nothing else surfaces it either) live in a "Progressive Web App"
  block gated behind `base.group_no_one` - invisible unless developer
  mode is on.

## How it works

- A one-attribute `t-inherit` on `web.webclient_bootstrap` points the
  `apple-touch-icon` `href` at a new `/web/pwa_icon/apple-touch-icon.png`
  route. That route looks for whichever sized PNG `web_pwa_customize`
  already generated as an `ir.attachment` (it writes several - 128 up to
  512 - named `/web_pwa_customize/icon<W>x<H>.png`), picks the one
  closest to Apple's usual sizes, and redirects there; an SVG upload (not
  resized by `web_pwa_customize`) redirects to that instead; nothing
  configured at all falls back to Odoo's own `odoo-icon-ios.png`.
- The `pwa_settings` block's `groups="base.group_no_one"` is stripped via
  a one-line view inherit. General Settings itself already requires
  admin access, so this doesn't expose anything that wasn't already
  admin-only - it just stops requiring developer mode on top of that.

No model, no icon storage of our own - `web_pwa_customize` already owns
that, this module only reads what it wrote.

## Setup

Install `web_pwa_customize` from OCA/web (19.0) first (see that
module's own README for icon/size requirements - notably: real PNGs
need to be at least 512x512, or upload an SVG instead), then this
module. **Settings → General Settings → Progressive Web App** - all
four fields (name, short name, colors, icon) are visible without
turning on developer mode.

## Known limitations

- The icon on the rarely-seen "you're offline" page (shown when the
  service worker serves a cached page with no connection) still uses
  Odoo's own artwork - not worth the complexity of wiring up for a page
  almost nobody sees.
- If you upload an SVG to `web_pwa_customize` (no size variants get
  generated for those), the apple-touch-icon route redirects straight to
  that SVG - most modern iOS versions render it fine, but it isn't a
  guarantee the way a real PNG is.
