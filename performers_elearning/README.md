# eLearning: Performers Training

Three courses for the Performers Suite, built into Odoo's eLearning app on
install (members only, by invitation, for salespeople), each with a quiz and
screenshots from a sample performer ("DJ Nova", "Nova Sounds"):

- **Bookings: From Request to Gig Day** (Gig Bookings): the Book a Date
  form, packages billed by the gig's hours, never booked twice, signature
  and deposit, the balance to-do, the timeline and the Gig Sheet.
- **Gear and Music** (Gig Gear Checklist, Gig Song Requests): the gear list,
  packing, the client's lists, song requests by QR code, Songs to Get.
- **Getting Booked Again** (Event Appearances, Website Press Kit):
  appearances, Promote It, the press kit page.

The data file is built by `tools/build_course_data.py` (it also builds
`performers_elearning_events`): edit the lessons there and rerun it when a
screen changes. Screenshots are in `static/img`.
