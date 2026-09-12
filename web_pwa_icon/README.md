# Progressive Web App Icon

Lets you set your own icon for Odoo's "Install app" / "Add to Home
Screen" prompt (Chrome, Edge, Android, iOS Safari) - normally hardcoded
to Odoo's own artwork with no visible Settings option to change it, even
though the app's *name* already is one (`web.web_app_name`) - it's just
sitting behind developer mode, in a "Progressive Web App" block nobody
stumbles across. This module surfaces that block unconditionally and
adds the icon field right next to the name one.

## How it works

Odoo reads the install icon from exactly two places, both of which this
module redirects to a new dynamic route once a custom icon is set:

- `/web/manifest.webmanifest` - the PWA manifest Chrome/Edge/Android use
  for "Install app". `WebManifest._get_webmanifest()` is overridden to
  point its `icons` list at `/web/pwa_icon/<size>` instead of the stock
  `odoo-icon-*.png` files, but **only when a custom icon is actually
  configured** - with nothing set, the manifest is byte-for-byte what
  core Odoo already served.
- the `apple-touch-icon` `<link>` tag in `web.webclient_bootstrap` - what
  iOS Safari uses for "Add to Home Screen". A one-attribute `t-inherit`
  points its `href` at `/web/pwa_icon/180x180` unconditionally (the route
  itself decides whether to serve your icon or fall back).

The new `/web/pwa_icon/<width>x<height>` route does the actual
decision: if `res.company.pwa_icon` is set, it streams that image
resized to the requested dimensions (via `ir.binary`'s existing
image-processing pipeline - the same one every other image field in
Odoo already uses); if not, it redirects to whichever of Odoo's own
`odoo-icon-*.png` files matches that size. One upload covers every size
Odoo asks for - nothing to pre-resize by hand.

## Setup

**Settings → General Settings → Progressive Web App**: set an app name
(this field, `web.web_app_name`, is core Odoo's own - this module just
makes the block it lives in visible without developer mode) and/or
upload a square icon, ideally 512x512 or larger, with little to no
transparency since some platforms mask it into a circle or squircle.
Leave the icon empty and that half changes nothing.

## Known limitations

- The icon on the rarely-seen "you're offline" page (shown when the
  service worker serves a cached page with no connection) still uses
  Odoo's own artwork. That page's icon is loaded from a literal file
  path via `file_open()`, not a URL, so serving a database-stored image
  there would mean caching a resized copy out to a real static file -
  not worth the complexity for a page almost nobody sees.
- One icon per company, not one for the whole database - in a
  multi-company install, each company can set its own (it's a
  `res.company` field), and the manifest/route always use whichever
  company `request.env.company` resolves to for that request.
