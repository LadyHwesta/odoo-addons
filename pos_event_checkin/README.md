# POS Event Check-in

The door, in the Point of Sale. Odoo's own **POS - Event** (`pos_event`)
already sells event tickets from the till. This adds checking in the people
who bought their tickets beforehand, so one person at the door can do both.
Built for DJ EmBass and the nonprofit events, 2026-11-16.

## Scan a ticket

Scan the ticket's barcode or QR code with the till's scanner, on the
register screen. It's checked in with the Events app's Registration Desk
rules, and the till shows the result:

- **Checked in** (green), with the name, ticket and event.
- **Already checked in** (amber), with the time.
- **Not today** (red): a ticket for another day, with its date.
- **Cancelled**, **Not confirmed** (never confirmed, e.g. unpaid) or
  **Event is over** (red).

A code that isn't a ticket goes on to the till's normal product scan, so
product barcodes work as before.

## The door list

**⋮ Actions > Check In** shows today's events with how many are in
("42 of 120 in"), a search by name, email, phone or ticket number, a
**Check in** button for each person, and **Scan** to use the device's camera
(phones and tablets).

## Which events

Today's events (in each event's own time zone) of the till's company that
aren't over. Tickets of another company's events are treated as unknown
codes. Any Point of Sale user can check people in at their own till.
