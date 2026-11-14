# -*- coding: utf-8 -*-
{
    'name': 'Calendar Meeting Documents',
    'version': '19.0.1.2.0',
    'category': 'Productivity/Calendar',
    'summary': 'Attach documents to meetings, show them on the calendar, and send them with invitations',
    'description': """
Calendar Meeting Documents
==========================

* A **Documents** tab on every meeting: add files (agenda, minutes,
  papers), download them, remove them. They belong to the meeting, so
  whoever can open the meeting can open them.
* The pop-up you get when clicking a meeting in the calendar lists them.
* **Send Documents with Invitations** (on by default): the documents are
  attached to the invitation, update and date-change emails Odoo sends
  attendees. Reminders and cancellations don't carry them. If they add up
  to more than 15 MB, the email says to open the meeting instead.
* **In the video call**: when the meeting's call opens, its documents are
  pinned in the call's chat as download links, so everyone (guests from the
  invitation link too) can open them on their own device. The list follows
  changes.
* **Private** documents stay on the meeting for your team: not emailed, not
  listed in the call. Making one private cancels any link already shared.
* Files attached with the chatter's paperclip, or sent in a reply to the
  invitation, join the meeting's documents.

Add-ons that install themselves when their apps are present:

* ``calendar_event_documents_dms``: link files from a DMS (Documents)
  folder, such as a team folder, instead of uploading copies.
* ``calendar_event_documents_onlyoffice``: Open in ONLYOFFICE on each
  document, and New Agenda / New Minutes buttons that create a Word
  document on the meeting and open it in the editor.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['calendar'],
    'data': ['views/calendar_event_views.xml'],
    'installable': True,
    'application': False,
}
