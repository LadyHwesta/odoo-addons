# Gig Bookings

For DJs, bands and other performers who get booked for events. Built for
DJ EmBass (djembass.com), 2026-11-16.

## The flow

1. **Request**: the **Book a Date** page (`/book`) is an ordinary Odoo
   website form (so Turnstile/reCAPTCHA protect it like any other) that
   creates a lead in the website's sales team, named after the gig
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
to-do once; the Booked Dates calendar. 12 tests. The form was also filled
and submitted in a real browser.

## License

LGPL-3.
