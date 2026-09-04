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

## Status — Phases 1 & 2 of 4

Phase 1 made an actor **discoverable**; Phase 2 makes it **publish and
gain followers**. Phase 3 adds inbound replies / likes / boosts; Phase 4
adds the event bridge + polish.

Implemented now:

- **`activitypub.actor`** — a federated identity scoped to a `website`. RSA
  2048 key pair generated on creation; the private key is a `base.group_system`
  field and is never served.
- **WebFinger** — `GET /.well-known/webfinger?resource=acct:<user>@<domain>`
  returns the JRD that points at the actor, scoped to the website whose
  domain the request arrived on.
- **NodeInfo** — `/.well-known/nodeinfo` + `/nodeinfo/2.1`.
- **Actor object** — `GET /ap/actors/<id>` served as
  `application/activity+json` to Fediverse servers, 302-redirected to the
  website for browsers (content negotiation on `Accept`).
- **Outbound publishing** — `activitypub.actor._ap_publish(...)` /
  `._ap_retract(...)` store a local `activitypub.object`, wrap it in a
  `Create` / `Update` / `Delete` `activitypub.activity`, and queue one
  `activitypub.delivery` per distinct follower inbox. A 1-minute cron signs
  each with HTTP Signatures and POSTs it, retrying transient failures with
  exponential backoff (8 attempts, ~2 h) and giving up permanently on a
  `4xx`. A daily cron prunes settled delivery rows.
- **Outbox** — `GET /ap/actors/<id>/outbox` is a real paged
  `OrderedCollection` of published activities; `/followers` reports the
  accepted followers.
- **Objects & activities** — `GET /ap/objects/<id>` (content-negotiated)
  and `GET /ap/activities/<id>` serve the stored JSON-LD.
- **Inbox** — `POST /ap/actors/<id>/inbox` and the shared `/ap/inbox`
  verify the HTTP Signature against the sending actor's fetched public key
  (SSRF-guarded, cached in `activitypub.remote.actor` for 24 h), reject a
  bad / stale / unowned signature with `401`, cap the body at 1 MiB, and
  dispatch **Follow** (records the follower, auto-sends `Accept`),
  **Undo{Follow}** (removes it) and **Accept**. Any other activity type is
  accepted and logged as ignored (`202`) — reply / like / boost handling is
  Phase 3.
- A master **Enable Fediverse federation** switch (Settings → Fediverse).
  While off, every endpoint above returns `404`.
- Debug views under **Fediverse**: Actors, Followers, Activities (with the
  raw payload and per-inbox delivery state), Delivery Queue.

### SSRF / abuse guards

Every outbound dereference (`fetch_json`, `post_activity`) goes through
`assert_public_url`, which resolves the host and refuses loopback, private,
link-local, multicast and reserved addresses; responses are size-capped
(2 MiB) and redirect-capped (3), with a `(5 s, 20 s)` timeout. A residual
DNS-rebinding time-of-check/use gap is documented in the code. The inbox
rejects unsigned requests and oversized bodies before doing any work.

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

Plain `unittest` (no Odoo, no DB), verified against the real `cryptography`
and `requests`:

- **HTTP Signatures / keys** (`test_http_signature.py`): sign↔verify round
  trips, body-tamper / stale-`Date` / wrong-key / wrong-target rejection,
  signed-GET shape.
- **JSON-LD builders** (`test_documents.py`, `test_activity_builders.py`):
  WebFinger, Actor, `OrderedCollection`, and the Create / Update / Delete /
  Accept / Reject envelopes.
- **SSRF guard** (`test_ssrf.py`, `getaddrinfo` monkeypatched): loopback,
  RFC-1918, link-local and IPv6 loopback are refused; a public address and
  an unresolvable host behave correctly.

`TransactionCase` / `HttpCase`:

- **Actor model** (`test_actor.py`): keypair on create, URLs from the
  website domain, username rules + per-website uniqueness, post-federation
  username lock.
- **Delivery** (`test_delivery.py`, `post_activity` mocked): publish queues
  one delivery per shared inbox; `2xx` → delivered, `5xx` / network error →
  scheduled retry (not re-tried before `next_attempt`), `4xx` → permanent
  fail; the parent activity's state follows its deliveries; no followers →
  activity settles as delivered.
- **Follow flow** (`test_follow_flow.py`, signature verification mocked,
  remote actor pre-seeded in cache): a signed Follow creates the follower
  and queues an `Accept`; it is idempotent; `Undo{Follow}` removes it; a
  bad signature or an unowned `keyId` is `401`; an unknown type is logged
  and `202`.
- **Controllers** (`test_controllers.py`, `test_outbox_http.py`):
  WebFinger, Actor content negotiation, NodeInfo, the master switch, the
  paged outbox / followers collections, and object / activity endpoints.
- **Blog bridge** — see `activitypub_website_blog`.
- Not yet exercised against a real remote server (Mastodon etc.) — that is
  the Phase 4 verification step.

Run them with:

```
odoo-bin -d <db> -i activitypub --test-enable --test-tags=/activitypub --stop-after-init
```

## Files

- `models/activitypub_service.py` — plain-Python protocol helpers: keys,
  HTTP Signatures, JSON-LD document + activity builders, content
  negotiation, and the SSRF-guarded `fetch_json` / `post_activity`. No Odoo
  import; unit-testable standalone.
- `models/activitypub_actor.py` — the `activitypub.actor` model, plus
  `_ap_publish` / `_ap_retract` (the entry points bridges call) and
  follower-inbox fan-out.
- `models/activitypub_object.py` — one row per federated object (local
  render of an Odoo record, or a stored remote object).
- `models/activitypub_activity.py` — Create/Update/Delete/Follow/… rows;
  `_queue_deliveries` for outbound, `_ingest` + `_ingest_<type>` for
  inbound.
- `models/activitypub_delivery.py` — one POST of an activity to one inbox;
  the `_cron_deliver` retry loop and `_cron_gc` pruner.
- `models/activitypub_follower.py` — a remote actor following a local one.
- `models/activitypub_remote_actor.py` — 24 h cache of dereferenced remote
  actors and their public keys.
- `controllers/well_known.py` — WebFinger + NodeInfo.
- `controllers/activitypub.py` — the `/ap` actor object, paged
  outbox / followers collections, object / activity endpoints, and the
  signature-verifying inbox.
