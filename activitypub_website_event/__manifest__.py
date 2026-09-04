# -*- coding: utf-8 -*-
{
    'name': 'ActivityPub - Website Events',
    'version': '19.0.1.1.0',
    'category': 'Marketing/Events',
    'summary': 'Federate published events to the Fediverse as Event objects',
    'description': """
ActivityPub bridge for Website Events
=====================================

Publishes ``event.event`` records to the Fediverse as ActivityStreams
``Event`` objects (the shape Mobilizon, Gancio and friends consume), using
the ``activitypub`` engine.

* An **event category** (``event.type``) gets a *Federate events as* actor -
  typically a ``Group`` actor people follow for that programme of events.
  Each event inherits it and can override it per-event.
* Publishing an event on the website sends a ``Create``; editing its name,
  dates, description, location or tags sends an ``Update``; unpublishing or
  deleting it sends a ``Delete``.
* The Event object carries ``startTime`` / ``endTime``, the description as
  ``content``, the venue as a ``Place`` (with latitude / longitude when the
  address is geolocated), the cover image as an ``attachment``, and the
  event tags as ``Hashtag``s.
* ``event.event`` is a mail thread, so Fediverse replies to a federated
  event land in its chatter (see the engine's *Post federated replies to
  chatter* setting).

Install ``activitypub`` first and configure at least one actor.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'images': ['static/description/banner.png'],
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['activitypub', 'website_event'],
    'data': [
        'views/event_views.xml',
    ],
    'installable': True,
    'application': False,
}
