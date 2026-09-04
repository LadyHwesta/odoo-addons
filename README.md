# Odoo Addons

Custom Odoo 19 modules.

## Modules

- [`caldav_calendar/`](caldav_calendar/) - two-way calendar sync with any
  RFC 4791 CalDAV server (Nextcloud, Radicale, Baïkal, Fastmail, iCloud, ...).
- [`auth_imap/`](auth_imap/) - authenticate existing Odoo users against an
  IMAP mail server (mailbox password as a fallback login method).
- [`activitypub/`](activitypub/) - federate this Odoo instance into the
  Fediverse (Mastodon, Pleroma, Mobilizon, ...) over ActivityPub. The
  engine: actors, discovery, HTTP Signatures, delivery, inbox. Publishes no
  content on its own - install a bridge alongside it:
  - [`activitypub_website_blog/`](activitypub_website_blog/) - federate
    published blog posts.
  - [`activitypub_website_event/`](activitypub_website_event/) - federate
    published events.

  Start with [`activitypub/README.md`](activitypub/README.md); for a
  from-scratch setup against a real Fediverse server, follow
  [`TESTING_FEDERATION.md`](TESTING_FEDERATION.md) end to end.

## Testing

[`testing/`](testing/) has a self-contained local Odoo 19 + Postgres
instance for trying these modules against a real server - see
[`testing/README.md`](testing/README.md).

## Compatibility & contributing

Everything here targets **Odoo 19.0** (see each module's `__manifest__.py`
- the `19.0.x.y.z` version already encodes that), tracked on `main`. That's
the version actively used and maintained.

Ports to other Odoo versions (e.g. 18.0) are welcome as PRs, but should
target a new version branch (e.g. `18.0`) rather than `main` - ask if that
branch doesn't exist yet and it'll get created. The expectation is that
whoever contributes a version port also owns keeping it compatible going
forward: reviews/merges happen here, but active maintenance of a
non-current-version branch isn't something to expect from the `main`
maintainer.

## License

LGPL-3 (see [`LICENSE`](LICENSE)), matching Odoo Community itself, unless a
module's own manifest says otherwise.
