# Telehealth Booking

A deliberately small base module: one field
(`res.users.telehealth_video_tier`, Basic/Premium) and one hook point
(`calendar.event._get_premium_video_url`). Installed by itself, every
booking uses Odoo's own built-in Discuss video calling exactly as it
already works today - nothing about that behavior changes. A bridge
module (see [`telehealth_booking_signalwire`](../telehealth_booking_signalwire/))
fills the hook in to offer a real upgrade path.

## Why split it this way

A provider who's happy with free, built-in video should never have to
install anything else, configure a vendor account, or see a feature
they don't want. The reverse also matters: this module has zero
knowledge of SignalWire (or anything else) - `_get_premium_video_url`
returns nothing on its own, so a "Premium" tier with no bridge module
installed is silently, safely identical to "Basic." The upsell only
exists once you choose to add it.

## What actually happens when a booking needs a video link

`calendar.event._set_discuss_videocall_location()` - confirmed by
reading Odoo 19's own `calendar_event.py` to be the *real* entry point
(the "Add a video call" button in the Calendar UI is a frontend-JS
stub that calls this on save; the automatic compute chain
[`_compute_videocall_location`/`videocall_source`] is circular on a
brand-new event and isn't something to rely on triggering reliably
from server-side code) - is overridden here: a premium-tier
organizer's event gets one real chance at `_get_premium_video_url()`
first, and Discuss is always the fallback either way, base module or
not. An explicit `action_get_telehealth_video_link()` button gives
staff a direct, reliable way to request a link without depending on
the UI's own automatic behavior.

## The real reason a "Premium" tier is worth building at all

Discuss's own video calling is **peer-to-peer WebRTC**, not a server-
side relay - confirmed by reading `mail.ice.server`'s own code. With
no TURN server configured (self-hosted `coturn`, or a separate Twilio
Network Traversal Service account - Odoo's own fallback, not something
this module touches), calls between people on restrictive networks
(corporate firewalls, some mobile carriers, strict home routers)
simply fail to connect. That's fine for internal team calls; for a
real, paid, patient-facing booking product, a call that won't connect
is lost business. See `telehealth_booking_signalwire`'s own README for
the concrete alternative.

## Testing

`_set_discuss_videocall_location`'s own override (basic tier, premium
tier with no bridge installed, a mixed batch of both) and the explicit
action button are covered by tests. Nothing here makes any external
call - this module doesn't know any vendor exists.
