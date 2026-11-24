#!/usr/bin/env python3
"""Odoo Apps Store listings for the modules in this repo that go on the store.

For each module in LISTINGS this writes static/description/index.html (the
store page), and for modules marked art=True an icon.png (512x512) and
banner.png (1280x640) in the style of caldav_calendar's; it also sets the
manifest's name (25 characters at most, a store rule), images and support.

Store rules followed (apps.odoo.com/apps/vendor-guidelines, read 2026-11-15):
English only; no JavaScript, iframes or external links except mailto:; images
from static/description only; no promotions. Every page ends with the same
support note (free modules; support through a support contract).

    python3 tools/store_listing.py            # all modules
    python3 tools/store_listing.py dmarc_report
Needs rsvg-convert (brew install librsvg).
"""
import html
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUPPORT_EMAIL = 'sales@meskis.net'
PURPLE_A, PURPLE_B, INK = '#7f5bbf', '#4c2e78', '#4a2f7a'

# Feather-style 24x24 glyphs (stroke drawings).
GLYPHS = {
    'heart_plus': '<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 0 0-7.8 7.8l1 1.1L12 21l7.8-7.8 1-1.1a5.5 5.5 0 0 0 0-7.8z"/><path d="M12 9.5v6M9 12.5h6"/>',
    'mail_check': '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="M22 6l-10 7L2 6"/><path d="M15 18l2 2 4-4"/>',
    'folders': '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M8 13h8M8 16h5"/>',
    'folder_web': '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><circle cx="12" cy="14" r="3.2"/><path d="M8.8 14h6.4"/>',
    'template': '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h5"/>',
    'bell': '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/>',
    'gallery': '<rect x="2" y="4" width="9" height="7" rx="1.5"/><rect x="13" y="4" width="9" height="7" rx="1.5"/><rect x="2" y="13" width="9" height="7" rx="1.5"/><rect x="13" y="13" width="9" height="7" rx="1.5"/>',
    'reload': '<path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/>',
    'link': '<path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/>',
    'graduation': '<path d="M22 10L12 5 2 10l10 5 10-5z"/><path d="M6 12v5c3 2 9 2 12 0v-5"/>',
    'meeting_docs': '<rect x="3" y="4" width="18" height="17" rx="2"/><path d="M16 2v4M8 2v4M3 10h18M8 15h8M8 18h5"/>',
    'eye_off': '<path d="M17.9 17.9A10 10 0 0 1 12 20c-7 0-11-8-11-8a18 18 0 0 1 5.1-5.9M9.9 4.2A9 9 0 0 1 12 4c7 0 11 8 11 8a18 18 0 0 1-2.2 3.2"/><path d="M1 1l22 22"/>',
    'user_check': '<circle cx="9" cy="7" r="4"/><path d="M2 21v-2a4 4 0 0 1 4-4h6a4 4 0 0 1 4 4v2"/><path d="M16 11l2 2 4-4"/>',
    'send': '<path d="M22 2L11 13"/><path d="M22 2l-7 20-4-9-9-4z"/>',
    'shield': '<path d="M12 2l8 3v6c0 5-3.4 9.4-8 11-4.6-1.6-8-6-8-11V5z"/><path d="M9 12l2 2 4-4"/>',
    'query': '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6V14"/><path d="M12 17.5h.01"/>',
    'mic': '<rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10a7 7 0 0 0 14 0"/><path d="M12 17v5M8 22h8"/>',
    'gauge': '<path d="M12 14l4-4"/><path d="M3.3 19a10 10 0 1 1 17.4 0"/>',
    'checklist': '<rect x="4" y="3" width="16" height="19" rx="2"/><path d="M9 2h6v3H9z"/><path d="M8 11l2 2 4-4"/><path d="M8 17h8"/>',
    'music': '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
    'sun': '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    'ticket': '<path d="M3 8a2 2 0 0 0 2-2h14a2 2 0 0 0 2 2v2a2 2 0 0 0 0 4v2a2 2 0 0 0-2 2H5a2 2 0 0 0-2-2v-2a2 2 0 0 0 0-4z"/><path d="M9 10l2 2 4-4"/>',
    'press': '<path d="M4 4h13v16H6a2 2 0 0 1-2-2z"/><path d="M17 8h3v10a2 2 0 0 1-2 2"/><path d="M8 8h5M8 12h5M8 16h3"/>',
}

# module -> listing. art=False keeps the module's existing icon and banner.
LISTINGS = {
    'caldav_calendar': dict(name='CalDAV Calendar Sync', art=False),
    'activitypub': dict(name='Fediverse (ActivityPub)', art=False),
    'activitypub_website_blog': dict(name='Fediverse: Blog Posts', art=False),
    'activitypub_website_event': dict(name='Fediverse: Events', art=False),
    'auth_imap': dict(name='IMAP Authentication', art=False),
    'dmarc_report': dict(
        name='DMARC Reports', glyph='mail_check',
        tagline='Read DMARC reports and explain them in plain language',
        intro=['Mail providers such as Google and Microsoft send daily DMARC reports to the '
               'address in your domain\'s DMARC record. They are XML files nobody reads.',
               'This module reads each report as it arrives and tells you, in plain language, '
               'who sent email as your domain, what passed, what failed, and what to fix.'],
        features=[('Reports read for you', 'Point an incoming mail server at the reporting mailbox; '
                   'every report becomes a DMARC report record with its findings.'),
                  ('Plain-language findings', 'Each sender is named with what it means and what to '
                   'change, instead of raw SPF and DKIM results.'),
                  ('No outside service', 'Reports stay in your own Odoo: no third-party DMARC '
                   'dashboard needed.')],
        setup=['Create a mailbox for DMARC reports and put its address in your domain\'s DMARC '
               'record (rua=mailto:...).',
               'In Settings, add an Incoming Mail Server for that mailbox, set to create DMARC Reports.',
               'Open DMARC Reports to see each report and its findings.']),
    'web_app_drawer_folders': dict(
        name='App Folders and Order', glyph='folders',
        tagline='Put apps in your own order and group them into folders',
        intro=['Odoo lists apps in its own order, and module upgrades reset any order you set by hand.',
               'This module lets you drag every app into the order you want and group them into '
               'named folders, and keeps that order through upgrades.'],
        features=[('Your order', 'Drag apps into the order your team uses them; apps outside a '
                   'folder come first.'),
                  ('Folders', 'Name folders such as "Money", "Phones" or "Events" and drag them into '
                   'order.'),
                  ('Kept through upgrades', 'The order lives in its own records, so upgrading '
                   'modules doesn\'t undo it.')],
        setup=['Go to Settings, Users &amp; Companies, App Drawer.',
               'Drag apps and folders into order, and save.']),
    'web_app_drawer_folders_website': dict(
        name='App Folders: Website', glyph='folder_web',
        tagline='Your app folders in the apps menu on website pages',
        intro=['Signed-in staff see an apps menu at the top of website pages. With this module it '
               'shows the same folders and order as the backend, from App Folders and Order.'],
        features=[('Same folders everywhere', 'Folder headings and your app order in the website '
                   'apps menu.'),
                  ('Nothing to set up', 'It follows the folders you set in App Folders and Order.')],
        setup=['Install it next to App Folders and Order and Website; there is nothing else to set.']),
    'mail_template_menu': dict(
        name='Email Templates Menu', glyph='template',
        tagline='Edit email templates from Settings, without developer mode',
        intro=['Odoo\'s Email Templates screen is simple once you are on it, but the menu to reach it '
               'is under Settings, Technical, which needs developer mode.',
               'This module adds a plain Email Templates menu directly under Settings, for anyone '
               'with Odoo\'s own Mail Template Editor permission.'],
        features=[('A normal front door', 'Email Templates sits next to General Settings.'),
                  ('No new permissions', 'It uses Odoo\'s existing Mail Template Editor group.'),
                  ('No developer mode', 'Staff edit wording without turning on developer mode.')],
        setup=['Give the person the Mail Template Editor permission on their user.',
               'They open Settings, Email Templates.']),
    'account_invoice_payment_reminder': dict(
        name='Invoice Payment Reminders', glyph='bell',
        tagline='Automatic reminder emails for unpaid customer invoices',
        intro=['A simple reminder schedule for customer invoices: a few named stages, each a number '
               'of days before or after the due date, with its own email.',
               'Every day, each unpaid invoice gets whichever stage is due, once per stage.'],
        features=[('Ready to use', 'Four stages out of the box, from a friendly note before the due '
                   'date to a final notice.'),
                  ('Your wording', 'Each stage has its own email template you can edit.'),
                  ('Once per stage', 'An invoice never gets the same reminder twice, and paid '
                   'invoices get none.')],
        setup=['Install it; the four stages are created for you.',
               'Adjust the days and wording of each stage in the Accounting settings if you like.']),
    'discuss_call_layout': dict(
        name='Video Call Gallery View', glyph='gallery',
        tagline='Gallery and Speaker view for Discuss video calls, like Zoom and Teams',
        intro=['Discuss video calls get the two views people know from other video apps: Gallery, '
               'with everyone tiled, and Speaker, where whoever is talking fills the screen.'],
        features=[('One button', 'Switch views from the call\'s controls; each person\'s choice '
                   'is remembered on their device.'),
                  ('Back after screen sharing', 'When a screen share ends, the call returns to the '
                   'chosen view instead of staying on the presenter.'),
                  ('For guests too', 'Works for people who join from a meeting invitation link.')],
        setup=['Install it, and start or join a video call: the Gallery / Speaker button is in the '
               'call controls.']),
    'web_reload_on_upgrade': dict(
        name='Reload After Upgrades', glyph='reload',
        tagline='Open Odoo windows and installed apps reload themselves after an upgrade',
        intro=['After an upgrade, windows that were already open keep running the old screens until '
               'someone reloads them, and the installed (PWA) app often has no reload button.',
               'This module notices the upgrade and reloads the window for you.'],
        features=[('Notices upgrades', 'Checks when the window comes back to the front, when the '
                   'connection reconnects, and every ten minutes.'),
                  ('Saves first', 'Saves the open record before reloading; if it can\'t, or a dialog '
                   'is open, it asks instead.'),
                  ('Fresh screens', 'Clears the browser caches so the new screens load.')],
        setup=['Install it; there is nothing to set up.']),
    'http_route_args_guard': dict(
        name='Missing Argument Guard', glyph='query',
        tagline="Requests missing a page's required values get a plain 404, not a server error",
        intro=['Odoo hands the values in a request straight to the page\'s code. When a page needs a '
               'value the request doesn\'t carry, such as /scoped_app without app_id, nothing checks '
               'first: the code crashes, the visitor gets a server error and your log a traceback. '
               'Real visitors never send these requests; scanners send them all day.',
               'This module checks every request before the page runs. If a required value is '
               'missing, the answer is a plain 404, which isn\'t logged as an error.'],
        features=[('Every page at once', 'Covers every page and JSON-RPC call, including ones added '
                   'by other modules later.'),
                  ('Quiet logs', 'Scanner traffic stops filling your log with tracebacks and '
                   'setting off error alerts.'),
                  ('Nothing else changes', 'Requests that carry what the page needs work exactly as '
                   'before.'),
                  ('Installs itself', 'It installs automatically with Odoo\'s web client.')],
        setup=['Install it; there is nothing to set up.']),
    'website_event_appearance': dict(
        name='Event Appearances', glyph='mic',
        tagline="List events you're performing at: link to the host's tickets, show their flyer",
        intro=['Performers, speakers and vendors appear at events someone else runs. Listing those '
               'as normal events makes Odoo try to sell tickets and take registrations for them.',
               'Mark an event as an appearance and it is listed on your website with your own events, '
               'but nothing is sold here: the page shows who is hosting, their flyer and materials, '
               'and a button to where people buy tickets or register.'],
        features=[('Link to the host', 'Get tickets, Register or More info, opening the host\'s page; '
                   'or Free entry.'),
                  ('Their flyer and materials', 'Images and files from the host, on the event page.'),
                  ('A badge in your events list', 'Shown on each appearance, e.g. "Performing".'),
                  ('Nothing sold by mistake', 'Odoo\'s registration and tickets are switched off for '
                   'appearances, even if someone posts to them directly.')],
        setup=['Install it, open an event and tick Appearance.',
               'Choose how people get in and paste the host\'s link.']),
    'sale_gig_booking': dict(
        name='Gig Bookings', glyph='mic',
        tagline='Booking requests for performers: gig details, e-signed quotes with a deposit, no double bookings',
        intro=['For DJs, bands and other performers booked for events. A request form on your website '
               'creates a lead with the gig: date, times, venue, type of event and guests.',
               'Quotes carry the same details, Odoo\'s own online signature and deposit book the date, and '
               'every date is checked against your other gigs and events first.'],
        features=[('Booking request form', 'A ready Book a Date page on your website, protected like any '
                   'other Odoo form.'),
                  ('Never booked twice', 'Gigs, appearances and events too close together are flagged, '
                   'and confirming one is stopped until you say so.'),
                  ('Booked Dates calendar', 'Every confirmed gig and event in one place.'),
                  ('Balance reminders', 'A to-do to invoice what\'s left, a set number of days before each gig.')],
        setup=['Install it, and turn on Online Signature and Online Payment (with a deposit) in Sales settings.',
               'Link your website to the Book a Date page (/book).']),
    'sale_gig_gear': dict(
        name='Gig Gear Checklist', glyph='checklist',
        tagline='Your gear list, default gear per package, and a packing checklist on every gig',
        intro=['Keep a list of the gear you take to gigs: speakers, lights, mics, cables, and how many '
               'of each you own. On each package or add-on, say which gear it needs.',
               'Every booked gig then gets its own packing checklist, and the load-in sheet prints it '
               'with boxes to tick as it goes in the van.'],
        features=[('Checklist on every gig', 'Filled from the booked packages when the gig is confirmed; '
                   'add or change items by hand.'),
                  ('Packed ticks', '"5 of 12 packed" at a glance, and a printed list to tick on the day.'),
                  ('More than you own', 'A gig needing more of something than you have is flagged.'),
                  ('Load-in sheet', 'Times, venue, on-site contact, notes and gear, on one page.')],
        setup=['Install it (it needs Gig Bookings) and add your gear in Sales > Configuration > Gear.',
               'Open each package product and list its gear on the Gig Gear tab.']),
    'sale_gig_song_requests': dict(
        name='Gig Song Requests', glyph='music',
        tagline='Guests request songs from a QR code; clients set must-play and do-not-play lists',
        intro=['Every booked gig gets a private song request page and a QR card to stand on the tables. '
               'Guests request a song from their phone, and the page closes when the gig ends.',
               'Before the gig, your client fills in must-play and do-not-play lists from their customer '
               'portal. You see everything on the gig, and requests on the do-not-play list are flagged.'],
        features=[('QR card for the tables', 'Print it from the gig; it opens the request page on your '
                   'own website.'),
                  ('Protected and rate-limited', 'Turnstile or reCAPTCHA if you use them, a hidden bot trap, '
                   'and a limit per phone.'),
                  ('Client music lists', 'Must play (with the moment, e.g. First dance) and do not play, '
                   'from the customer portal until the gig starts.'),
                  ('Songs to Get', 'Mark each song Got it, or Can\'t get with a reason the client sees.'),
                  ('Played or skipped', 'One tap per request during the gig.')],
        setup=['Install it (it needs Gig Bookings).',
               'On a booked gig, open the Music tab and use Print Song Card.']),
    'website_press_kit': dict(
        name='Website Press Kit', glyph='press',
        tagline='A press kit page for performers: bio, photos to download, links, upcoming shows, Book button',
        intro=['Promoters, venues and journalists ask every act for the same things: a bio, photos, '
               'something to listen to, and dates. This module puts them on one page of your website, '
               'at /press-kit.',
               'Your upcoming events appear on it by themselves, and photos download at full size, so '
               'they print well.'],
        features=[('Bio, genres, where you\'re based', 'With booking email and phone.'),
                  ('Photos at full size', 'Shown at web size on the page; Download gives the original, '
                   'with your caption and photo credit.'),
                  ('Mixes, videos and socials', 'Links grouped as buttons; a technical rider to download.'),
                  ('Upcoming events', 'Published events on this website, appearances included, '
                   'straight from your Events app.'),
                  ('Your theme, one kit per website', 'Laid out with your website\'s colors; each '
                   'website has its own.')],
        setup=['Install it and open Website > Site > Press Kit.',
               'Fill it in, tick Published, and add /press-kit to your website menu.']),
    'pos_event_checkin': dict(
        name='POS Event Check-in', glyph='ticket',
        tagline='Check people in at the door from the Point of Sale: scan their ticket or look them up',
        intro=['Odoo\'s Point of Sale already sells event tickets at the door. This adds the other half: '
               'checking in the people who bought their tickets beforehand, at the same till.',
               'Scan a ticket and it\'s checked in with the Registration Desk\'s rules, or open the door '
               'list to find someone by name and see how many are in.'],
        features=[('Scan to check in', 'Scanner or the device\'s camera; product barcodes still work.'),
                  ('Clear answers', 'Checked in, already in (and when), another day\'s ticket, cancelled '
                   'or unconfirmed.'),
                  ('The door list', 'Today\'s attendees with search and a running "42 of 120 in".'),
                  ('Today and your company only', 'Other days\' and other companies\' tickets are never '
                   'checked in by mistake.')],
        setup=['Install it (it needs POS - Event) and open your Point of Sale.',
               'Scan a ticket on the register screen, or use Actions > Check In.']),
    'website_donation_cover_fees': dict(
        name='Donor Covers the Fees', glyph='heart_plus',
        tagline='Let donors add the card fees to their gift, so the whole gift arrives',
        intro=['Card payments cost a percentage plus a few cents, so a $25 online gift arrives as '
               'a little less. Many donors are glad to make up the difference if asked.',
               'This adds an unticked "I\'ll cover the processing fees" box to the website\'s '
               'Donation block, showing the exact extra amount. If the donor ticks it, the payment '
               'is grossed up so that, after the fees, the full gift is left.'],
        features=[('The exact amount, up front', 'The box shows "+$1.06" for the gift chosen, and '
                   'updates as the amount changes.'),
                  ('Unticked by default', 'Donors choose; nobody pays extra without noticing.'),
                  ('Worked out on the server', 'The browser only previews; the amount charged is '
                   'calculated again when the payment starts.'),
                  ('Gift and fees kept apart', 'Each payment records the gift and the fees covered '
                   'separately, for receipts and reports.'),
                  ('Your rates', 'Set the processing percentage and fixed amount in Website settings.')],
        setup=['Install it (it needs Website Payment).',
               'Website > Configuration > Settings > Donors Can Cover the Fees: check the rates.']),
    'my_day': dict(
        name='My Day', glyph='sun',
        tagline='A start screen to plan and work through your day, across your companies and branches',
        intro=['Today\'s calendar and your to-dos on one side; what needs attention on the other: tasks '
               'coming due, money owed and due, quotes waiting on customers, this week\'s events.',
               'It follows the company switcher, so with several companies or branches selected you see '
               'them all, each item marked by company. Make it the first screen after login.'],
        features=[('Plan the day', 'Today\'s meetings with a Join button, to-dos you can tick off, voicemails and callbacks.'),
                  ('Needs attention', 'Helpdesk tickets, tasks due, money owed and due, quotes waiting, events.'),
                  ('Companies and branches', 'Money per company, a badge on every item, one tap to see one company.'),
                  ('Your start screen', 'One tick in Preferences opens it after login.'),
                  ('Only what you may see', 'Sections appear for installed apps and your access rights.')],
        setup=['Install it and open My Day.',
               'Tick Start on My Day in your Preferences to open it after login.']),
    'website_canonical_url_guard': dict(
        name='Canonical URL Guard', glyph='link',
        tagline='Bots probing odd addresses get a plain 404, not a server error',
        intro=['Odoo 19 builds each page\'s canonical link with a strict URL check. Bots probing '
               'addresses such as /a/%2e%2e/etc/passwd make that check fail, so the "page not '
               'found" page itself crashes: visitors get a server error and your log an error.',
               'This module falls back to your home page as the canonical link for those addresses, '
               'so the 404 page shows normally.'],
        features=[('Quiet logs', 'No more "Couldn\'t render a template for http status 404" errors '
                   'from bot traffic.'),
                  ('Normal pages unchanged', 'Real pages keep their usual canonical link.'),
                  ('Installs itself', 'It installs automatically with the Website app.')],
        setup=['Install it; there is nothing to set up.']),
    'website_slides_publication_digest': dict(
        name='eLearning Lesson Digest', glyph='graduation',
        tagline='One email per course for new lessons, not one per lesson',
        intro=['Odoo announces a lesson to the course\'s members whenever it is saved as published, '
               'even when it already was. Courses installed as modules are saved again on every '
               'update, so each update emailed every lesson again.'],
        features=[('Only real news', 'A lesson is announced only when it becomes published.'),
                  ('One digest per course', 'Lessons added by a module install or update go out as '
                   'one message per course, with links.'),
                  ('By hand, as before', 'Publishing a lesson yourself still sends its normal '
                   'announcement.')],
        setup=['Install it; there is nothing to set up.']),
    'calendar_event_documents': dict(
        name='Meeting Documents', glyph='meeting_docs',
        tagline='Attach documents to meetings and send them with invitations',
        intro=['A Documents tab on every meeting for the agenda, minutes and papers, shown on the '
               'calendar and sent with the invitation.'],
        features=[('On the meeting', 'Add, download and remove files on a Documents tab; whoever '
                   'can open the meeting can open them.'),
                  ('With invitations', 'Documents are attached to invitation and update emails '
                   '(over 15 MB, the email says to open the meeting instead).'),
                  ('In the video call', 'They are pinned in the call\'s chat as download links, '
                   'for guests too.'),
                  ('Private documents', 'Keep a file for your team only: not emailed and not '
                   'shown in the call.')],
        setup=['Open a meeting in Calendar and use its Documents tab.']),
    'mail_no_hidden_preview': dict(
        name='No Hidden Email Preview', glyph='eye_off',
        tagline='Remove the hidden preview text spam filters score against',
        intro=['Odoo\'s notification emails start with a hidden block of preview text padded with '
               'invisible characters. Spam filters such as SpamAssassin count that as a spammer '
               'trick.',
               'This module empties that block, so inboxes preview the start of the message itself.'],
        features=[('Fewer spam points', 'Removes a rule worth half of the score that marks mail '
                   'as spam.'),
                  ('Better previews', 'Inbox previews show the message itself.'),
                  ('Mailings untouched', 'Email Marketing\'s own preview text field is left alone.')],
        setup=['Install it; there is nothing to set up.']),
    'project_task_partner_assignee': dict(
        name='Assign Tasks to Contacts', glyph='user_check',
        tagline='Make a contact responsible for a task or subtask',
        intro=['Odoo\'s task assignees are internal users only. This module adds a Contact Assignee '
               'to tasks and subtasks, so a client, volunteer or partner can be the one responsible.'],
        features=[('Any contact', 'Pick any contact as the task\'s assignee, separate from its '
                   'customer.'),
                  ('Kept in the loop', 'The contact follows the task, so its chatter emails reach them.'),
                  ('Tasks and subtasks', 'Works the same on both.')],
        setup=['Open a task and choose its Contact Assignee.']),
    'mailing_list_welcome': dict(
        name='Mailing List Welcome', glyph='send',
        tagline='A welcome email for each new website newsletter signup',
        intro=['Pick an Email Marketing mailing as a list\'s welcome email. Everyone who signs up '
               'through a website newsletter block then gets it once.'],
        features=[('Sent once', 'Each new subscriber gets the welcome email one time.'),
                  ('Unsubscribe built in', 'It carries Odoo\'s normal unsubscribe link and one-click '
                   'unsubscribe headers.'),
                  ('Protects the owner', 'If someone signs up an address that isn\'t theirs, its owner '
                   'can leave with one click.')],
        setup=['Write the welcome email as a mailing in Email Marketing.',
               'On the mailing list, choose it as the Welcome Email.']),
    'security_auth_guard': dict(
        name='Security Auth Guard', glyph='shield',
        tagline='Login attempts on record, and repeat attackers blocked for good',
        intro=['Odoo slows down repeated failed logins, but only in memory: the count is lost on every '
               'restart, and the block is always temporary.',
               'This module keeps every login attempt on record, logs security events, and blocks an '
               'address for good once it keeps attacking.'],
        features=[('Every login on record', 'Successful and failed logins, with address and login '
                   'name, kept and reportable.'),
                  ('Permanent blocks', 'An address that triggers Odoo\'s slowdown too often in a day '
                   'is blocked, before any page runs.'),
                  ('Scanners blocked', 'An address that asks for files only attackers look for, '
                   'such as /.env or /wp-login.php, is blocked for a day; repeat scanners for good. '
                   'Search engines never ask for these, so indexing is unaffected.'),
                  ('Allow and block lists', 'Add your own allowed or blocked addresses.'),
                  ('One security log', 'Events in a Security app, by severity, to review.'),
                  ('Errors that explain themselves', 'Each request error in the log gets one line '
                   'naming the error, the page and whether a signed-in user or a bot caused it.')],
        setup=['Install it, then open the Security app.',
               'Adjust login and scanner blocking in its settings, or keep the defaults.']),
    'security_auth_guard_dashboard': dict(
        name='Security Dashboard', glyph='gauge',
        tagline='A threat level, failed logins and blocks in the Dashboards app',
        intro=['Adds a Security dashboard to the Dashboards app, built on Security Auth Guard.'],
        features=[('Threat level', 'One reading of how much attention logins need today.'),
                  ('At a glance', 'Failed logins, blocks and events waiting for review.')],
        setup=['Install it next to Security Auth Guard, and open Dashboards, Security.']),
}

SUPPORT_HTML = f'''
<section class="oe_container oe_dark">
    <div class="oe_row oe_spaced">
        <div class="oe_span12">
            <h3 class="oe_slogan">Support</h3>
            <p class="oe_mt32" style="text-align:center;">
                This module is free. Help installing, setting up or using it is available from
                Meskis Works with a support contract:
                <a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a>.
            </p>
        </div>
    </div>
</section>
'''
SUPPORT_MARK = '<h3 class="oe_slogan">Support</h3>'


def icon_svg(glyph):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">'
            f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{PURPLE_A}"/>'
            f'<stop offset="1" stop-color="{PURPLE_B}"/></linearGradient></defs>'
            f'<rect width="512" height="512" rx="96" fill="url(#g)"/>'
            f'<g transform="translate(106 106) scale(12.5)" fill="none" stroke="#ffffff" stroke-width="1.9" '
            f'stroke-linecap="round" stroke-linejoin="round">{GLYPHS[glyph]}</g></svg>')


def wrap(text, width):
    lines, line = [], ''
    for word in text.split():
        if len(line) + len(word) + 1 > width and line:
            lines.append(line)
            line = word
        else:
            line = f'{line} {word}'.strip()
    return lines + [line]


def banner_svg(glyph, name, tagline):
    title_size = 64 if len(name) <= 20 else 56
    tag = ''.join(f'<text x="476" y="{372 + i * 52}" font-size="36" fill="#ffffff">{html.escape(l)}</text>'
                  for i, l in enumerate(wrap(tagline, 36)[:3]))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="640" viewBox="0 0 1280 640" '
            f'font-family="Helvetica Neue, Helvetica, Arial, sans-serif">'
            f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{PURPLE_A}"/>'
            f'<stop offset="1" stop-color="{PURPLE_B}"/></linearGradient></defs>'
            f'<rect width="1280" height="640" fill="url(#g)"/>'
            f'<rect x="96" y="170" width="300" height="300" rx="56" fill="#f8f6fc"/>'
            f'<g transform="translate(146 220) scale(8.33)" fill="none" stroke="{INK}" stroke-width="1.9" '
            f'stroke-linecap="round" stroke-linejoin="round">{GLYPHS[glyph]}</g>'
            f'<text x="476" y="300" font-size="{title_size}" font-weight="700" fill="#ffffff">{html.escape(name)}</text>'
            f'{tag}</svg>')


def render(svg_text, target):
    subprocess.run(['rsvg-convert', '-o', str(target)], input=svg_text.encode(), check=True)


def page(name, spec):
    def p(text):
        return f'<p>{text}</p>'
    feats = spec['features']
    rows = []
    for i in range(0, len(feats), 2):
        cells = ''.join(f'<div class="oe_span6"><h3 class="oe_slogan">{t}</h3><p>{d}</p></div>'
                        for t, d in feats[i:i + 2])
        rows.append(f'<div class="oe_row oe_spaced">{cells}</div>')
    steps = ''.join(f'<li>{s}</li>' for s in spec['setup'])
    return f'''<section class="oe_container">
    <div class="oe_row oe_spaced">
        <h2 class="oe_slogan" style="color:{INK};">{name}</h2>
        <h3 class="oe_slogan" style="color:#666;">{spec['tagline']}</h3>
        <div class="oe_span12">
            <p class="oe_mt32" style="text-align:center;">
                <img src="banner.png" class="img img-responsive" style="max-width:100%;border-radius:8px;" alt="{name}"/>
            </p>
        </div>
    </div>
</section>

<section class="oe_container oe_dark">
    <div class="oe_row oe_spaced">
        <div class="oe_span12">
            <h3 class="oe_slogan">What it does</h3>
            {''.join(p(t) for t in spec['intro'])}
        </div>
    </div>
</section>

<section class="oe_container">
    {''.join(rows)}
</section>

<section class="oe_container">
    <div class="oe_row oe_spaced">
        <div class="oe_span12">
            <h3 class="oe_slogan">Setting it up</h3>
            <ol>{steps}</ol>
        </div>
    </div>
</section>
{SUPPORT_HTML}'''


def set_manifest(module, name):
    path = ROOT / module / '__manifest__.py'
    text = path.read_text()
    text = re.sub(r"(['\"]name['\"]\s*:\s*)(['\"])(.*?)\2", lambda m: f"{m.group(1)}'{name}'", text, count=1)
    if "'images'" not in text and '"images"' not in text:
        text = re.sub(r"(\n(\s*)['\"]license['\"]\s*:[^\n]*\n)",
                      lambda m: f"{m.group(1)}{m.group(2)}'images': ['static/description/banner.png'],\n",
                      text, count=1)
    if "'support'" not in text and '"support"' not in text:
        text = re.sub(r"(\n(\s*)['\"]license['\"]\s*:[^\n]*\n)",
                      lambda m: f"{m.group(1)}{m.group(2)}'support': '{SUPPORT_EMAIL}',\n", text, count=1)
    path.write_text(text)


def build(module):
    spec = LISTINGS[module]
    desc = ROOT / module / 'static' / 'description'
    desc.mkdir(parents=True, exist_ok=True)
    set_manifest(module, spec['name'])
    index = desc / 'index.html'
    if spec.get('art', True):
        if not (desc / 'icon.png').exists():
            # An existing icon (e.g. a Settings-section icon) is kept.
            render(icon_svg(spec['glyph']), desc / 'icon.png')
        render(banner_svg(spec['glyph'], spec['name'], spec['tagline']), desc / 'banner.png')
        index.write_text(page(spec['name'], spec))
    elif SUPPORT_MARK not in index.read_text():
        # Hand-written page: add the support note at the end.
        index.write_text(index.read_text().rstrip() + '\n' + SUPPORT_HTML)
    assert len(spec['name']) <= 25, module
    print(module)


def check(root):
    """Store-rule problems for every listed module under `root`
    (this repo, or the store repo's copy): [] when all is well."""
    import ast
    import os
    problems = []
    for module, spec in LISTINGS.items():
        base = Path(root) / module
        try:
            manifest = ast.literal_eval((base / '__manifest__.py').read_text())
            page_html = (base / 'static' / 'description' / 'index.html').read_text()
        except (OSError, ValueError, SyntaxError) as exc:
            problems.append(f'{module}: {exc}')
            continue
        if len(manifest.get('name', '')) > 25:
            problems.append(f'{module}: name longer than 25 characters')
        if not str(manifest.get('version', '')).startswith('19.0.'):
            problems.append(f'{module}: version must start with 19.0.')
        if manifest.get('license') not in ('LGPL-3', 'AGPL-3', 'GPL-3', 'OPL-1'):
            problems.append(f'{module}: license')
        for dep in manifest.get('depends', []):
            if (Path(root) / dep).is_dir() and dep not in LISTINGS:
                problems.append(f'{module}: depends on {dep}, which is not on the store')
        for image in manifest.get('images', []) + ['static/description/icon.png']:
            if not (base / image).exists():
                problems.append(f'{module}: missing {image}')
        if re.search(r'<script|<iframe|javascript:', page_html, re.I):
            problems.append(f'{module}: script or iframe in index.html')
        for ref in re.findall(r'(?:href|src)="([^"]+)"', page_html):
            if ref.startswith('mailto:') or re.match(r'https://(www\.)?youtube\.com/', ref):
                continue
            if re.match(r'[a-z]+:', ref):
                problems.append(f'{module}: external link {ref}')
            elif not (base / 'static' / 'description' / ref).exists():
                problems.append(f'{module}: missing {ref}')
    return problems


if __name__ == '__main__':
    if sys.argv[1:2] == ['--check']:
        found = check(sys.argv[2] if len(sys.argv) > 2 else ROOT)
        print('\n'.join(found) or 'All store listings pass.')
        sys.exit(1 if found else 0)
    if sys.argv[1:2] == ['--list']:
        print(' '.join(LISTINGS))
        sys.exit(0)
    for module in sys.argv[1:] or LISTINGS:
        build(module)
