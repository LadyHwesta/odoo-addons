# Event Appearances

For performers, speakers and vendors who appear at events someone else
runs. Mark an event as an **Appearance** and it's listed on your website
alongside your own events, but nothing is sold or registered in Odoo.

## What an appearance shows

- **Hosted by**: the venue, promoter or organisation (a contact).
- **Getting in**: tickets sold by the host, registration with the host, a
  link for more information, or free entry. The event page's button
  ("Get tickets", "Register", "More info", or your own text) opens the
  host's page in a new tab; free entry just says so.
- **Marketing materials**: the host's flyers, posters and press images,
  shown under the description. Attaching them makes them public, so
  anyone viewing the page can open them. Use the event's cover image for
  the main flyer.
- **Badge**: shown on the event in the events list ("Performing" by
  default).

## What's switched off

For an appearance, `event_registrations_open` is always false, so Odoo's
own Register button, tickets and "Registrations Closed" notices don't
show, and the registration routes (`/registration/new`,
`/registration/confirm`) answer 404 even if posted directly. The Tickets
tab is hidden on the form. Everything else about the event (dates, venue,
map, description, tags, website) works as usual.

## Built for

DJ EmBass (djembass.com), 2026-11-16: gigs she's hired for were going
through the normal event system, which wanted to sell tickets.

## Testing

`tests/test_appearance.py`: registrations closed only for appearances, the
event page links to the host with no "closed" notice, the flyer shows,
the events list shows the badge, direct registration posts are refused,
materials become public, the host becomes the organizer, link rules. 7 tests.

## License

LGPL-3.
