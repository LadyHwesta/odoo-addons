# -*- coding: utf-8 -*-
{
    'name': 'Public Meetings',
    'version': '19.0.1.1.0',
    'category': 'Productivity/Calendar',
    'summary': 'Meetings the public can watch: a view-only link, sign-in with name and email',
    'description': """
Public Meetings
===============

For meetings open to the public, such as a nonprofit's board meeting or a
community briefing. Tick **Public Meeting** on a meeting and it runs in a paid
video room:

- **Speakers**, the meeting's attendees, join from the link in their
  invitation and can talk, use their camera and share their screen.
- **The public** use the meeting's **Watch Link**, which can go on a website
  or in a newsletter. They give their name and email, then watch and listen;
  they can't speak, show video or share a screen.
- Before joining, speakers check their camera, microphone and speaker; in
  the meeting, **Settings** switches them.
- A side panel: the speakers' **Chat** (speakers only), **Questions** sent by
  viewers (a speaker can put one on everyone's screen while answering it),
  and the meeting's **Documents**. Speakers can add documents during the
  meeting; they join the meeting's Documents tab.
- The **Public** tab lists everyone who signed in to watch, and keeps the
  questions and chat.
- The meeting's documents that aren't private are listed on both pages.

Up to 299 viewers per meeting, set per meeting (the room holds 300 people).
Every speaker and viewer is billed per minute on the video service. Needs the
phone service connection (signalwire_voip) with video allowed on its API token.
""",
    'author': 'Meskis Works',
    'website': 'https://meskis.net',
    'license': 'LGPL-3',
    'depends': ['calendar_event_documents', 'signalwire_voip', 'website'],
    'data': [
        'security/ir.model.access.csv',
        'views/calendar_event_views.xml',
        'views/templates.xml',
    ],
    'installable': True,
}
