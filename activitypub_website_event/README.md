# ActivityPub – Website Events

Federates `website_event` events to the Fediverse as ActivityStreams
`Event` objects (the shape [Mobilizon](https://joinmobilizon.org/) and
Gancio consume), on top of the [`activitypub`](../activitypub) engine.

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
override wins. Not yet run against a real Mobilizon / Mastodon instance —
see `../TESTING_FEDERATION.md`.

## Files

- `models/event_type.py` — the `activitypub_actor_id` field on the category.
- `models/event_event.py` — the per-event actor (defaulted from the
  category), plus the `Event` builder and location/place mapping. Lifecycle
  hooks come from `activitypub.federatable`.
