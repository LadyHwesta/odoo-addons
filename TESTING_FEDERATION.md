# End-to-end federation test (Odoo ↔ Mastodon)

The `activitypub*` modules are covered by ~80 automated tests, but real
federation only proves out against another live server. This is the manual
pass to run once, against a Mastodon (or Mobilizon) instance you control.

## 0. Prerequisites

- Odoo 19 reachable at **`https://<DOMAIN>`** with a **valid TLS cert**,
  where `<DOMAIN>` is exactly the **Website Domain** you'll configure. The
  reverse proxy must forward `/.well-known/*` and `/ap/*` to Odoo untouched.
- A Mastodon account on an instance that can reach `<DOMAIN>` over HTTPS.
- `activitypub` + a bridge (`activitypub_website_blog` and/or
  `activitypub_website_event`) installed.

> **Same-LAN test rigs:** the SSRF guard refuses private / loopback
> addresses, so Odoo will not deliver to a Mastodon on `10.x` / `192.168.x`.
> Put both behind public DNS + TLS, **or** add the peer's hostname to
> *Settings → Fediverse → SSRF allowlist*.

## 1. Configure Odoo

1. **Settings → Website** → set **Domain** to `https://<DOMAIN>` for the
   website you're federating.
2. **Settings → Fediverse** → tick **Enable Fediverse federation**. Leave
   *Post federated replies to chatter* on.
3. **Fediverse → Actors → New**: pick that website, type **Service** (a
   site voice) or **Group** (a feed), username e.g. `news`. Save. Note the
   **Actor URL** (`https://<DOMAIN>/ap/actors/<ID>`).
4. **Settings → Technical → Scheduled Actions**: confirm
   *ActivityPub: deliver queued activities* is active (every 1 min). You
   can **Run Manually** to push instantly during testing.

## 2. Discovery (from any shell)

```sh
DOMAIN=your.domain
# WebFinger resolves the handle -> actor URL
curl -s "https://$DOMAIN/.well-known/webfinger?resource=acct:news@$DOMAIN" \
  -H 'Accept: application/jrd+json' | jq

# Actor doc: must have publicKey.publicKeyPem, inbox, endpoints.sharedInbox
curl -s "https://$DOMAIN/ap/actors/1" \
  -H 'Accept: application/activity+json' | jq '{id, type, preferredUsername, inbox, publicKey: .publicKey.id}'
```

Both must return `200` and valid JSON. A browser hitting the actor URL
(no `Accept: …activity+json`) should 302 to the website instead.

## 3. Follow from Mastodon

1. In Mastodon search, enter `@news@<DOMAIN>`. The profile should resolve
   (0 posts is fine). Click **Follow**.
2. Within a minute (or after a manual cron run), in Odoo:
   - **Fediverse → Followers** lists your Mastodon account.
   - **Fediverse → Activities**: an inbound `Follow` (state *processed*) and
     an outbound `Accept` (state *delivered*).
   - **Fediverse → Delivery Queue**: the Accept row is *delivered*.
3. Mastodon should now show you as following (not "pending").

## 4. Publish

**Blog:** Website → Blog → set the blog's **Federate posts as** to the
actor. Create a post, **Publish** it. Within ~1 min it lands in your
Mastodon home timeline. Check the Delivery Queue row is *delivered*, and
**Fediverse → Objects** shows a `Note` (not `Article` - see the gotcha
below) with the reply/like/boost counters.

**Events:** Events → Configuration → Event Templates → set a category's
**Federate events as**. Create an event in that category, publish it on the
website. It federates as a proper `Event` object for Mobilizon / Gancio.
On Mastodon specifically, expect the same non-rendering behavior as
`Article` below - Mastodon's Create handler doesn't materialize a status
for `Event` either, so followers there may see nothing for it. That's a
Mastodon limitation with structured Event federation in general, not a bug
here; if visible Mastodon posts for events matter to you, say so and the
event bridge can be changed to also emit a `Note`.

> **Gotcha found during testing:** Mastodon's `Create` handler only turns
> `Note` (and `Question`, for polls) into a visible status. Other types -
> `Article` included - are accepted and even counted in the profile's post
> count, but never appear in the timeline or the Posts tab. Confirmed via
> `GET /api/v1/accounts/<id>/statuses` returning `[]` while `statuses_count`
> was `1`. The blog bridge sends `Note` for exactly this reason.

## 5. Interaction back

- **Reply** to the federated post from Mastodon → within a minute the reply
  shows in the record's **chatter** in Odoo, and in **Fediverse → Objects**
  as a remote object threaded under the parent.
- **Favourite / Boost** it → the parent object's **Likes / Boosts** counts
  increment (Objects list).
- **Edit** the post in Odoo → an `Update` is delivered; Mastodon marks it
  edited. **Unpublish** or delete it → a `Delete`; Mastodon removes it.

## 6. If something's stuck

| Symptom | Look at |
|---|---|
| Handle won't resolve in Mastodon | `curl` step 2 from outside your network; TLS cert; proxy passing `/.well-known/webfinger` |
| Follower never appears | Odoo log for `odoo.addons.activitypub` — signature failures log at INFO; check the inbox got the POST (proxy/access log) |
| Accept/posts never delivered | **Delivery Queue** row's *Last error* + *Attempts*; run the cron manually; SSRF allowlist if peer is private |
| `429` in the peer's logs | inbound rate limit (120 / 60 s per remote actor) — only trips under a real flood |
| Reply not in chatter | *Post federated replies to chatter* setting; the reply's `inReplyTo` must be the object's `id` URL, which it is for anything that federated from here |
