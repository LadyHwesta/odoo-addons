# ActivityPub / Fediverse Federation

Federate an Odoo instance into the Fediverse (Mastodon, Pleroma, Misskey,
Mobilizon, …) over [ActivityPub](https://www.w3.org/TR/activitypub/).

This module is the **engine**. It publishes no Odoo content on its own —
that is the job of the bridge modules:

| Module | Maps |
|---|---|
| `activitypub` (this one) | actors, keys, discovery, HTTP Signatures, the `/ap` endpoints |
| `activitypub_website_blog` | `blog.post` → `Article` |
| `activitypub_website_event` | `event.event` → `Event` |

No extra pip packages: only `requests` and `cryptography`, both already
bundled with Odoo.

## Status — Phase 1 of 4

Phase 1 makes an actor **discoverable**. Later phases add outbound
publishing + follows (2), inbound replies/likes/boosts (3), and the event
bridge + polish (4). See the design notes in the repo discussion.

Implemented now:

- **`activitypub.actor`** — a federated identity scoped to a `website`. RSA
  2048 key pair generated on creation; the private key is a `base.group_system`
  field and is never served.
- **WebFinger** — `GET /.well-known/webfinger?resource=acct:<user>@<domain>`
  returns the JRD that points at the actor. Scoped to the website whose
  domain the request arrived on.
- **NodeInfo** — `/.well-known/nodeinfo` + `/nodeinfo/2.1`.
- **Actor object** — `GET /ap/actors/<id>` served as
  `application/activity+json` to Fediverse servers, 302-redirected to the
  website for browsers (content negotiation on `Accept`).
- **Collections** — `/ap/actors/<id>/{outbox,followers,following}` return
  empty `OrderedCollection`s for now.
- **Inbox** — `POST /ap/actors/<id>/inbox` and `/ap/inbox` accept and log
  with `202`; signature verification and dispatch land in Phase 2.
- A master **Enable Fediverse federation** switch (Settings → Fediverse).
  While off, every endpoint above returns `404`.

## Multi-website / multi-domain

An actor's handle host is the **Website Domain** of its `website_id`
(*Settings → Website → Domain*, e.g. `https://news.acme.com`), falling back
to `web.base.url` when that is blank. So one Odoo instance federates each
branch under its own domain — `@news@acme.com`, `@events@acme.eu`, … — as
long as every such domain terminates TLS and routes to this Odoo. The
module does not manage DNS or the reverse proxy.

Changing a website's domain, or an actor's `username`, after federation has
started **breaks every existing follow**: remote servers keyed the follow
to the old actor URI. The `username` is locked automatically once anything
has been published under it (`federated_once`).

## Setup

1. Install `activitypub`.
2. *Settings → Website* — make sure each website that should federate has
   its **Website Domain** set to the public `https://…` URL.
3. *Settings → Fediverse* — tick **Enable Fediverse federation**.
4. *Fediverse → Actors* — create an actor: pick the website, a type
   (`Service` for "the website itself"), and a `username`.
5. From a Mastodon account, search for `@<username>@<domain>`. The profile
   should resolve (with 0 posts until the bridge modules are installed).

## Testing status

- **HTTP Signatures / key helpers** (`tests/test_http_signature.py`) and
  **JSON-LD builders / content negotiation** (`tests/test_documents.py`)
  are plain `unittest` — no Odoo, no DB — covering sign↔verify round trips,
  body-tamper and stale-`Date` rejection, wrong-key rejection, signed-GET
  shape, and the WebFinger / Actor document structure. Verified against the
  real `cryptography` package.
- **Actor model** (`tests/test_actor.py`, `TransactionCase`): keypair
  generated on create and parseable, URLs derived from the website domain,
  username lowercasing / validation / per-website uniqueness, and the
  post-federation username lock.
- **Controllers** (`tests/test_controllers.py`, `HttpCase`): WebFinger
  resolves a known actor and 404s an unknown one, the Actor endpoint
  content-negotiates JSON vs a browser redirect, the collections are empty,
  NodeInfo discovery works, and the master switch hides everything when off.
- Not yet exercised against a real remote server — that starts to matter in
  Phase 2 when actual delivery exists.

Run them with:

```
odoo-bin -d <db> -i activitypub --test-enable --stop-after-init
```

## Files

- `models/activitypub_service.py` — plain-Python protocol helpers (keys,
  HTTP Signatures, JSON-LD document builders, content negotiation). No Odoo
  import; unit-testable standalone.
- `models/activitypub_actor.py` — the `activitypub.actor` model.
- `controllers/well_known.py` — WebFinger + NodeInfo.
- `controllers/activitypub.py` — the `/ap` actor object, collections, and
  the placeholder inbox.
