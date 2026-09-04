# ActivityPub – Website Events

Federates `website_event` events to the Fediverse as ActivityStreams
`Event` objects (the shape [Mobilizon](https://joinmobilizon.org/) and
Gancio consume), on top of the [`activitypub`](../activitypub) engine.

> **On Mastodon specifically, expect to see nothing.** Confirmed against a
> real Mastodon instance (for the blog bridge, which hit the same
> mechanism): its `Create` handler only ever turns `Note` (or `Question`,
> for polls) into a visible status - every other type, `Event` included,
> is accepted but never rendered, silently and without error. That's a
> Mastodon limitation with structured event federation in general, not a
> bug here - `Event` is the *correct* type for Mobilizon/Gancio, which is
> what this bridge targets. If visible Mastodon posts for events matter to
> you too, say so - the bridge can be changed to also emit a `Note`
> alongside the `Event`, the way the blog bridge already does for posts.

## What it does

- Adds **Federate events as** (`activitypub_actor_id`) to the **event
  category** (`event.type`) — typically a `Group` actor people follow for
  that programme of events. Each event copies it on creation into its own
  **Federate as** field and can override it per event.

  | Event change | Sent to followers |
  |---|---|
  | published on the website | `Create` (Event) |
  | name / dates / description / location / tags edited while published | `Update` |
  | unpublished or deleted | `Delete` (Tombstone) |

- The `Event` object carries `name`, `summary` (subtitle), `content`
  (description), `startTime` / `endTime`, `url`, the venue as a `Place`
  (with `latitude` / `longitude` when the address partner is geolocated),
  the cover image as an `attachment`, and event tags as `Hashtag`s.

  Unlike the blog bridge, `summary` here is deliberately used for the
  subtitle. The "Mastodon reads `summary` as a content warning" trap
  (see `activitypub_website_blog`) applies to `Note`/`Article` -
  microblog-shaped objects a timeline renders as a single collapsible
  post. Mobilizon and Gancio, the intended consumers of `Event`, use
  `summary` as a genuine short description for event listings - the
  convention this vocabulary term actually documents.

- `event.event` is a mail thread, so Fediverse replies to a federated event
  land in its chatter (engine setting *Post federated replies to chatter*).

## Setup

1. Install this module (pulls in `activitypub` and `website_event`).
2. Create an `activitypub.actor` (Fediverse → Actors) — e.g. a `Group`
   actor `@events@yourdomain` on the right website.
3. On an event category (Events → Configuration → Event Templates), set
   **Federate events as**.
4. Publish an event in that category. Within a minute the delivery cron
   signs and POSTs a `Create` to every follower's inbox.

## Testing status

`tests/test_event_federation.py` (`TransactionCase`): the category actor is
inherited by new events; publishing creates an `Event` object with
`startTime` / `endTime` / `attributedTo` and queues delivery; a venue
becomes a `Place`; editing dates sends `Update`; unpublishing sends
`Delete`; an unpublished event federates nothing; a per-event actor
override wins.

This bridge itself has not been separately run against a real Mobilizon /
Gancio instance — see `../TESTING_FEDERATION.md`. It shares the engine's
publish/retract machinery with `activitypub_website_blog`, which *has*
been live-verified against Mastodon, including the fix that made
republishing after unpublish actually work (a `Create` after a `Delete`
now always gets a fresh object URI) - that part of the behavior is
exercised, just not this bridge's own `Event`-specific rendering on a real
event-federation consumer.

## Files

- `models/event_type.py` — the `activitypub_actor_id` field on the category.
- `models/event_event.py` — the per-event actor (defaulted from the
  category), plus the `Event` builder and location/place mapping. Lifecycle
  hooks come from `activitypub.federatable`.
