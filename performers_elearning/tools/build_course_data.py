"""Builds the performer courses' data files from the content below.

Run from the repository root after changing a lesson:

    python3 performers_elearning/tools/build_course_data.py

It writes performers_elearning/data/slide_channel_data.xml (the Performers
Suite courses) and performers_elearning_events/data/slide_channel_data.xml
(the Performer Events course). Keep lessons in step with the screens: when a
menu or button is renamed, change it here and rebuild.
"""
import os
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---- lesson building blocks (classes styled by course_content.scss) ----

def p(text):
    return f'<p>{text}</p>'


def path(*steps):
    return '<span class="oe-path">' + ' › '.join(escape(s) for s in steps) + '</span>'


def callout(icon, label, text, kind=''):
    cls = f'oe-callout oe-callout-{kind}' if kind else 'oe-callout'
    return (f'<div class="{cls}"><span class="oe-callout-icon"><i class="fa {icon}" /></span>'
            f'<div><span class="oe-callout-label">{escape(label)}</span><p>{text}</p></div></div>')


def shot(module, image, alt, caption):
    return (f'<div class="oe-diagram"><img src="/{module}/static/img/{image}" alt="{escape(alt)}" class="img-fluid" />'
            f'<p class="oe-diagram-caption"><span class="oe-diagram-caption-tag">Screenshot</span>{caption}</p></div>')


def flow(*steps):
    parts = []
    for i, (icon, text) in enumerate(steps):
        if i:
            parts.append('<span class="oe-flow-arrow"><i class="fa fa-long-arrow-right" /></span>')
        parts.append(f'<div class="oe-flow-step"><span class="oe-flow-step-icon"><i class="fa {icon}" /></span>'
                     f'{escape(text)}</div>')
    return '<div class="oe-diagram"><div class="oe-flow">' + ''.join(parts) + '</div></div>'


M = 'performers_elearning'
E = 'performers_elearning_events'

# ---- the courses ----
# course: (xmlid, name, description, enroll group xmlid, [sections]), section: (name, [lessons]),
# lesson: (name, html), quiz: [(question, [answers], index of the right one)]

BOOKINGS = ('channel_bookings', "Bookings: From Request to Gig Day",
    "Take a booking request to a signed, paid, never-double-booked gig, and walk into the day with everything on one sheet.",
    'sales_team.group_sale_salesman', [
    ("Requests and quotes", [
        ("The Book a Date form", ''.join([
            p("Clients ask for a date on your website's " + path("Book a Date") + " page (<code>/book</code>): "
              "their name and contact, the type of event, the date, start and end times, the venue, the number "
              "of guests and anything you should know."),
            shot(M, 'book_form.png', "The Book a Date form on the website", "the Book a Date page."),
            p("Each request becomes a lead in " + path("CRM") + ", named after the gig, with all of that on its "
              "<strong>Gig</strong> details. Add the page to your website menu once, and it's protected from "
              "spam like any other Odoo form."),
            callout('fa-clock-o', "Times past midnight", "An end time earlier than the start means the gig "
                    "runs past midnight: 21:00 to 01:00 is a four-hour gig."),
            callout('fa-building-o', "More than one business?", "Choose where this website's requests go in " +
                    path("Website", "Configuration", "Settings") + ", <strong>Booking Requests Go To</strong>. "
                    "The lead and its quote belong to that team's company, so they use that company's settings "
                    "and agreement terms."),
        ])),
        ("Packages and quotes", ''.join([
            p("From the lead, " + path("New Quotation") + " starts a quote with the gig's details already on "
              "its <strong>Gig</strong> tab. Pick a quote template for the package, and add-ons from its "
              "optional products."),
            p("Packages priced by the hour bill the gig's own length. On the product's " + path("Gigs") +
              " tab, tick <strong>Bill the Gig's Hours</strong>: a 17:00 to 23:00 gig puts 6 hours on the quote, "
              "and changing the gig's times changes the hours while it's still a quote. A "
              "<strong>Minimum Hours</strong> setting in " + path("Sales", "Configuration", "Settings") +
              " keeps short gigs from billing less."),
            shot(M, 'quote_lines.png', "A quote with an hourly package at six hours and a PA rental",
                 "an hourly package at the gig's 6 hours, and a flat-priced PA rental."),
            shot(M, 'product_gigs_tab.png', "A product's Gigs tab", "a package's <strong>Gigs</strong> tab: hourly "
                 "billing, a to-do when booked, and its gear."),
            callout('fa-check-square-o', "A to-do when booked", "<strong>To-do When Booked</strong> on a product "
                    "becomes a to-do for the salesperson the moment a gig with it is booked: for example, "
                    "\"Get the venue's equipment list\" for a sound engineer working on house gear."),
        ])),
        ("Never booked twice", ''.join([
            p("Every quote is checked against your confirmed gigs, your appearances and your own events, with a "
              "gap around each (set as <strong>Gap Between Gigs</strong> in Settings, 2 hours by default) for "
              "setup, travel and pack-down. Anything too close shows at the top of the quote."),
            shot(M, 'double_booking.png', "A quote warning that the date is already booked",
                 "a quote that clashes with a gig already booked that night."),
            p("Confirming a clashing quote is stopped; if you really mean it (two short sets, say), use "
              "<strong>Confirm Anyway</strong>. " + path("Sales", "Orders", "Booked Dates") +
              " shows every booked gig and event on a calendar."),
        ])),
    ]),
    ("Booked: signature, deposit and balance", [
        ("Signature and deposit", ''.join([
            p("Send the quote from Odoo. With <strong>Online Signature</strong> and <strong>Online Payment</strong> "
              "on (Settings, with the deposit as a percentage), the client signs and pays the deposit from the "
              "link, and that books the date: the quote becomes a sales order."),
            flow(('fa-paper-plane', "Send the quote"), ('fa-pencil', "Client signs"),
                 ('fa-credit-card', "Pays the deposit"), ('fa-calendar-check-o', "Date booked")),
            callout('fa-bell', "The balance", "A daily job adds an <strong>Invoice the balance</strong> to-do on "
                    "each booked gig coming up within <strong>Invoice Balance Before</strong> days (Settings, 14 by "
                    "default)."),
        ])),
    ]),
    ("On the day", [
        ("The timeline", ''.join([
            p("The quote's <strong>Timeline</strong> tab holds the moments of the event: grand entrance, first "
              "dance, toasts, last song. Times after midnight sort after the evening."),
            shot(M, 'timeline_tab.png', "A gig's timeline", "a wedding's timeline."),
            p("Clients add to it themselves from their order in the customer portal (<strong>Your event "
              "timeline</strong>) until the gig starts; their moments are marked <strong>From Client</strong>."),
        ])),
        ("The Gig Sheet", ''.join([
            p("The <strong>Gig</strong> tab also takes the load-in time, the on-site contact and load-in notes "
              "(parking, stairs, power, curfew). " + path("Print", "Gig Sheet") + " puts the whole day on paper: "
              "the booking, times, venue, contacts, what was booked, the timeline, the notes and the gear "
              "checklist, with the song request card as its last page."),
            shot(M, 'gig_sheet.png', "The Gig Sheet", "the start of a Gig Sheet."),
        ])),
    ]),
], [
    ("A wedding runs 17:00 to 23:00. How many hours does a package with Bill the Gig's Hours put on the quote?",
     ["6", "1", "Whatever the template says", "None until the gig is booked"], 0),
    ("A quote clashes with a gig already booked that night, and you're sure you can do both. What do you do?",
     ["Use Confirm Anyway", "Delete the other gig", "Change the gap in Settings to zero", "Send it without confirming"], 0),
    ("What books the date when Online Signature and Online Payment are on?",
     ["The client signing and paying the deposit", "Sending the quote", "The lead being created",
      "Printing the Gig Sheet"], 0),
    ("Where do clients add their grand entrance and first dance times?",
     ["Your event timeline, on their order in the customer portal", "The Book a Date form",
      "Songs to Get", "They email the Gig Sheet back"], 0),
])

GEAR_MUSIC = ('channel_gear_music', "Gear and Music",
    "Pack the right gear for every gig, and handle the client's music lists and guests' song requests.",
    'sales_team.group_sale_salesman', [
    ("Gear", [
        ("Your gear and each package's", ''.join([
            p("List your gear once in " + path("Sales", "Configuration", "Gear") + ": speakers, lights, mics, "
              "cables, and how many of each you own. Then, on each package or add-on, its " + path("Gigs") +
              " tab lists the gear it needs."),
            p("When a gig is booked, its <strong>Gear</strong> tab fills from the packages sold: two products "
              "each needing a speaker need two. <strong>Add Gear from Packages</strong> adds anything new (after "
              "an add-on, say) without removing what you added by hand."),
        ])),
        ("Packing", ''.join([
            p("Tick items off as they go in the van: \"2 of 6 packed\" at the top. Anything needing more than you "
              "own is flagged in red. The Gig Sheet prints the list with boxes to tick on the day."),
            shot(M, 'gear_tab.png', "A gig's gear checklist", "a gig's Gear tab, two items packed."),
        ])),
    ]),
    ("Music", [
        ("The client's lists", ''.join([
            p("Clients fill in two lists from their order in the customer portal: <strong>Must play</strong> "
              "(with the moment, like First dance) and <strong>Do not play</strong>. They can change them until "
              "the gig starts."),
            shot(M, 'portal_music.png', "The client's music lists in the portal", "the client's view."),
            p("Both lists are on the gig's <strong>Music</strong> tab too, for you to edit."),
        ])),
        ("Song requests from guests", ''.join([
            p("Every booked gig has a private song request page. " + path("Print Song Card") + " on the Music "
              "tab prints a card with its QR code for the tables (the Gig Sheet ends with one too)."),
            shot(M, 'song_request_phone.png', "The song request page on a phone", "what a guest sees."),
            p("Requests close when the gig ends, and each phone can send a few at a time. On the Music tab, or in "
              + path("Sales", "Orders", "Song Requests") + " during the gig, mark them <strong>Played</strong> "
              "or <strong>Skip</strong>; a request for a do-not-play song is shown in red."),
            shot(M, 'music_tab.png', "A gig's Music tab", "a gig's Music tab: the client's lists and guest requests."),
        ])),
        ("Songs to Get", ''.join([
            p(path("Sales", "Orders", "Songs to Get") + " lists the must-play songs and guest requests for "
              "upcoming gigs that you don't have yet. Mark each <strong>Got it</strong>, or <strong>Can't "
              "get</strong> with a note saying why: the client sees that note on their must-play list and can "
              "pick another song."),
            shot(M, 'songs_to_get.png', "Songs to Get", "songs still to get for an upcoming wedding."),
        ])),
    ]),
], [
    ("A package and an add-on each need one speaker. How many does the gig's gear checklist ask for?",
     ["2", "1", "None, gear is added by hand", "Whatever you own"], 0),
    ("You can't find a client's must-play song anywhere. What do you do?",
     ["Mark it Can't get with a note, so the client can choose another", "Delete it from their list",
      "Mark it Played", "Nothing, they'll notice on the night"], 0),
    ("When do guests stop being able to request songs?",
     ["When the gig ends", "When the gig starts", "A week before", "Never"], 0),
    ("A guest requests a song on the client's do-not-play list. How does it show?",
     ["In red, flagged as do-not-play", "It's refused on the guest's phone", "It goes on the must-play list",
      "It doesn't show at all"], 0),
])

PROMOTION = ('channel_promotion', "Getting Booked Again",
    "List the gigs you play at other people's events, and give promoters a press kit page.",
    'sales_team.group_sale_salesman', [
    ("Appearances", [
        ("Gigs at other people's events", ''.join([
            p("An event someone else runs, where you're performing, is an <strong>Appearance</strong>: tick it "
              "on the event. Your website lists it with your own events, with a badge (\"Performing\"), but "
              "nothing is sold or registered in Odoo."),
            p("On the " + path("Appearance") + " tab: the host, how people get in (tickets sold by the host, "
              "registration with the host, free entry, or just more information), the host's link and the "
              "button's label, and the host's flyer and materials to show on the page."),
            shot(M, 'appearance_form.png', "An event set up as an appearance", "an appearance at a festival."),
            callout('fa-bullhorn', "Promote It", "On a booked public gig, <strong>Promote It</strong> creates a "
                    "draft appearance from the gig: add the host's link and flyer, then publish it."),
        ])),
    ]),
    ("Press kit", [
        ("Your press kit page", ''.join([
            p("Promoters, venues and journalists all ask for the same things. " + path("Website", "Site",
              "Press Kit") + " puts them on one page, <code>/press-kit</code>: your bio, genres, where you're "
              "based, booking contacts, photos, mixes and videos, a technical rider and a Book button."),
            shot(M, 'press_kit_form.png', "The press kit form", "filling in the press kit."),
            p("Your upcoming events and appearances appear on it by themselves. Photos show at web size and "
              "download at full size, so they print well. Tick <strong>Published</strong> and add the page to "
              "your menu."),
            shot(M, 'press_kit_page.png', "The press kit page", "the published page, in the website's own colors."),
        ])),
    ]),
], [
    ("You're playing a festival run by someone else, who sells the tickets. How do you list it?",
     ["As an appearance, with the host's ticket link", "As an event selling tickets in Odoo",
      "As a quote", "On the press kit only"], 0),
    ("What does Promote It on a booked gig do?",
     ["Creates a draft appearance from the gig", "Publishes the press kit", "Emails the client",
      "Posts to social media"], 0),
    ("Where do your upcoming appearances show on the press kit page?",
     ["They appear by themselves", "You type them into the bio", "Only in the rider",
      "They don't"], 0),
    ("A promoter downloads a press photo. What size do they get?",
     ["The full-size original", "1024 pixels wide", "A thumbnail", "Whatever fits their screen"], 0),
])

EVENTS = ('channel_own_events', "Your Own Events: Paying Talent and the Door",
    "Pay the performers and staff of the events you run, and check people in at the door from the Point of Sale.",
    'event.group_event_user', [
    ("Paying performers and staff", [
        ("Fees and hours", ''.join([
            p("On your event's " + path("Entertainment") + " tab, each performance in a stage's running order "
              "takes a <strong>Fee</strong>. Only confirmed performances with a fee are owed. Hired staff, "
              "like a bartender, are paid by the hour: give their shift an <strong>Hourly Rate</strong> "
              "(Logistics), and once they check out, their hours times the rate are owed."),
            p("The tab shows what's owed and what's billed, and <strong>Bill Performers &amp; Staff</strong> "
              "makes one draft vendor bill per person for the event, ready to check and post in Accounting."),
            shot(E, 'event_payouts.png', "An event's Entertainment tab with what's owed",
                 "$550 owed, ready to bill."),
            callout('fa-file-text-o', "1099-NEC", "In the US, anyone billed this way who has no 1099 setting yet "
                    "is marked as a 1099-NEC vendor, so their payments add up in the 1099 summary. Untick it on "
                    "the contact for a corporation."),
            callout('fa-repeat', "Cancelled a bill?", "A line whose bill was cancelled can be billed again.",
                    'good'),
        ])),
    ]),
    ("The door", [
        ("Checking people in", ''.join([
            p("At the door, the same Point of Sale that sells tickets checks in the people who bought them "
              "beforehand. Scan a ticket on the register screen (scanner or camera) and it's checked in: green "
              "for checked in, amber if they're already in (with the time), red for a ticket for another day, "
              "cancelled, unconfirmed, or an event that's over."),
            p(path("⋮ Actions", "Check In") + " opens the door list: today's events with how many are in, a "
              "search by name, email, phone or ticket number, and a <strong>Check in</strong> button for each "
              "person."),
            shot(E, 'door_list.png', "The Check In list in the Point of Sale", "the door list, one of four in."),
            callout('fa-ticket', "Selling at the door", "Tickets sold at the door are an ordinary Point of Sale "
                    "sale: pick the event, the ticket and the guest's details."),
        ])),
    ]),
], [
    ("Which performances are owed on an event?",
     ["Confirmed performances with a fee", "Every performance on the running order",
      "Only those with a vendor bill", "Performances in the past"], 0),
    ("A bartender's shift is $25 an hour and they worked 4 hours. When are they owed $100?",
     ["Once they've checked out", "As soon as the shift is created", "When the event is published",
      "Never, staff aren't billed"], 0),
    ("You scan a ticket for next week's event at tonight's door. What happens?",
     ["It isn't checked in: the till shows the ticket's date", "It's checked in for next week",
      "The ticket is cancelled", "It's added to the order"], 0),
    ("Where's the door list with the running count?",
     ["Actions, Check In, in the Point of Sale", "The Events app's website", "Accounting", "The Gig Sheet"], 0),
])


# ---- writing the data ----

def course_xml(module, course, quiz):
    xmlid, name, description, group, sections = course
    out = [f'''    <record id="{xmlid}" model="slide.channel">
        <field name="name">{escape(name)}</field>
        <field name="channel_type">training</field>
        <field name="description" type="html"><p>{escape(description)}</p></field>
        <field name="visibility">members</field>
        <field name="enroll">invite</field>
        <field name="is_published" eval="True" />
        <field name="enroll_group_ids" eval="[(6, 0, [ref('{group}')])]" />
    </record>
''']
    seq = 0
    for s_index, (section, lessons) in enumerate(sections, 1):
        seq += 10
        out.append(f'''    <record id="{xmlid}_s{s_index}" model="slide.slide">
        <field name="channel_id" ref="{xmlid}" />
        <field name="is_published" eval="True" />
        <field name="name">{escape(section)}</field>
        <field name="is_category" eval="True" />
        <field name="sequence">{seq}</field>
    </record>
''')
        for l_index, (lesson, html) in enumerate(lessons, 1):
            seq += 1
            out.append(f'''    <record id="{xmlid}_s{s_index}_l{l_index}" model="slide.slide">
        <field name="channel_id" ref="{xmlid}" />
        <field name="is_published" eval="True" />
        <field name="name">{escape(lesson)}</field>
        <field name="slide_category">article</field>
        <field name="sequence">{seq}</field>
        <field name="html_content" type="html"><div class="oe-course-content">{html}</div></field>
    </record>
''')
    out.append(f'''    <record id="{xmlid}_quiz" model="slide.slide">
        <field name="channel_id" ref="{xmlid}" />
        <field name="is_published" eval="True" />
        <field name="name">Check what you've learned</field>
        <field name="slide_category">quiz</field>
        <field name="sequence">{seq + 50}</field>
    </record>
''')
    for q_index, (question, answers, right) in enumerate(quiz, 1):
        out.append(f'''    <record id="{xmlid}_q{q_index}" model="slide.question">
        <field name="slide_id" ref="{xmlid}_quiz" />
        <field name="sequence">{q_index}</field>
        <field name="question">{escape(question)}</field>
    </record>
''')
        for a_index, answer in enumerate(answers, 1):
            out.append(f'''    <record id="{xmlid}_q{q_index}_a{a_index}" model="slide.answer">
        <field name="question_id" ref="{xmlid}_q{q_index}" />
        <field name="sequence">{a_index}</field>
        <field name="text_value">{escape(answer)}</field>
        <field name="is_correct" eval="{a_index - 1 == right}" />
    </record>
''')
    return ''.join(out)


def write(module, courses):
    body = ''.join(course_xml(module, course[:5], course[5]) for course in courses)
    target = os.path.join(ROOT, module, 'data', 'slide_channel_data.xml')
    with open(target, 'w') as f:
        f.write('<?xml version="1.0" encoding="utf-8" ?>\n<!-- Built by performers_elearning/tools/'
                'build_course_data.py: edit there and rebuild. -->\n<odoo noupdate="1">\n\n' + body + '</odoo>\n')
    print(target)


if __name__ == '__main__':
    write(M, [BOOKINGS, GEAR_MUSIC, PROMOTION])
    write(E, [EVENTS])
