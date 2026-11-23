# Gig Bookings

For DJs, bands and other performers who get booked for events. Built for
DJ EmBass (djembass.com), 2026-11-16.

## The flow

1. **Request**: the **Book a Date** page (`/book`) is an ordinary Odoo
   website form (so Turnstile/reCAPTCHA protect it like any other) that
   creates a lead, named after the gig
   ("Booking request: Wedding 2027-02-14 Robin"). Times are offered in
   half hours; an end time earlier than the start means after midnight.
2. **Quote**: New Quotation from the lead starts with its gig details
   (Gig tab). Packages and add-ons are ordinary products and quote
   templates.
3. **Book**: Odoo's own **Online Signature** and **Online Payment** with
   a prepayment (deposit) percentage, set in Sales settings or per quote
   template. Paying the deposit confirms the order: the date is booked.
4. **Balance**: a daily job adds a to-do "Invoice the balance" to each
   booked gig coming up within *Invoice Balance Before* days (default 14),
   once.
5. **Promote It** (on a booked gig): creates a draft Appearance
   (`website_event_appearance`) for public gigs, to add the host's link
   and flyer and publish.

## Which sales team

Requests go to a team in the website's own company: the website's lead
team (set on a form in the website editor) if it belongs to that company,
otherwise its shop orders team (Website settings, eCommerce, Orders
Assignment), otherwise the company's first sales team. Found live on
djembass.com: the website belongs to the DJ Em Bass company while the
default lead team belonged to Meskis Works, and Odoo refused every
request.

## Never booked twice

Gig times are stored in UTC from the date, the start/end hours and the
company's **Gig Time Zone**. Anything closer than **Gap Between Gigs**
(default 2 hours: setup, travel, pack-down) to another booked gig or any
event (your own or an appearance) is listed on the lead and the quote.
A person confirming a clashing quote is stopped; **Confirm Anyway**
overrides. A deposit paid online still books it (the customer has paid),
with a chatter warning and a "Double booking" to-do. **Sales → Orders →
Booked Dates** shows every booked gig and event in one calendar.

Settings: Sales → Settings → Gig Bookings.

## Testing

`tests/test_gig_booking.py`: time zone and past-midnight times; clashes
with gigs, events and appearances; the confirm stop and Confirm Anyway;
deposit confirmation with a warning; quote defaults from the lead; the
website form creating a lead; the /book page; Promote It; the balance
to-do once; the Booked Dates calendar, the team for a website in another company. 13 tests. The form was also filled
and submitted in a real browser.

## License

LGPL-3.

## Timeline and Gig Sheet

The **Gig** tab holds the **load-in time**, the **on-site contact** and
**load-in notes** (parking, entrance, stairs, power, curfew). The
**Timeline** tab lists the moments of the event (18:00 Grand entrance,
18:15 First dance...); times up to the end of a gig that runs past midnight
sort after midnight. The client can add to the timeline from their order in
the customer portal (**Your event timeline**) until the gig starts.

**Print > Gig Sheet** puts everything on paper: the booking (reference,
status, total, who booked it), times, venue, every contact, what was booked,
the timeline and the load-in notes. Gig Gear Checklist (`sale_gig_gear`)
adds the gear checklist, and Gig Song Requests (`sale_gig_song_requests`)
adds the song request card as the last page.

## Hourly packages and booking to-dos

A product's **Gigs** tab:

- **Bill the Gig's Hours**: on a gig's quote, the quantity is the gig's
  length (start to end, to the quarter hour), and never below the
  **Minimum Hours** in Settings > Sales > Gig Bookings. It follows the gig's
  times while the quote is a draft or sent; once booked, the hours stay as
  agreed. Quote templates use it too.
- **To-do When Booked**: when a gig with this product is booked, the
  salesperson gets this to-do (first line: title; the rest: notes). For
  example: get the venue's equipment list and research it.
