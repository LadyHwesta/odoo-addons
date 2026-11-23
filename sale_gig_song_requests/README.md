# Gig Song Requests

Song requests from guests, and must-play and do-not-play lists from the
client. Needs **Gig Bookings** (`sale_gig_booking`).

## Guests

- Every gig has a private link, `https://<your website>/gig/<code>/songs`.
  It uses the website of the gig's company, so a DJ brand on its own website
  gets its own address. The **Music** tab on the gig shows the link and
  **Print Song Card** prints a page with its QR code for the tables.
- Guests give a song, an artist and their name (optional). Requests are taken
  from the moment the gig is booked until it ends. Untick **Take Song
  Requests** to switch them off for one gig.
- Protection: Turnstile or reCAPTCHA if the website uses them, a hidden field
  only bots fill in, at most 5 requests per phone in 10 minutes, and 500 per
  gig.
- **Sales > Orders > Song Requests** shows today's requests not played yet,
  with Played, Skip and Undo. A request for a song on the do-not-play list is
  shown in red.

## The client

The client's order in the customer portal has a **Music for your event**
card. It opens their **Must play** list (with the moment, e.g. First dance)
and **Do not play** list. They can change both until the gig starts. You can
also edit both lists on the gig's Music tab.

## Getting the tracks

**Sales > Orders > Songs to Get** lists the must-play songs and guest
requests for upcoming gigs that you don't have yet, grouped by gig. Mark each
**Got it**, or **Can't get** with a note saying why (for example "only a live
version exists"). The client sees that note on their must-play list, so they
can choose another song. **Undo** puts a song back on the list.

## Gig Sheet

The song request card prints as the last page of the gig's **Gig Sheet**
(when song requests are on for that gig). The song lists themselves aren't
printed: work from them online.
