# -*- coding: utf-8 -*-
{
    'name': 'Telehealth Booking - SignalWire Premium Video',
    'version': '19.0.1.0.0',
    'category': 'Services/Appointment',
    'summary': 'Upgrade path: SignalWire Video for telehealth bookings that outgrow Discuss',
    'description': """
Telehealth Booking - SignalWire Premium Video
================================================

Bridges ``telehealth_booking``'s own video-tier hook to real
SignalWire Video: a provider's self-service upgrade to Premium
provisions a real SignalWire subproject and a metered, post-paid
billing contract (reusing ``signalwire_voip_sale``'s own real, per-
record Call Detail Record + itemized PDF-statement mechanism - see
that module's own README - extended here to cover video room-session
usage, not just calls/SMS).

A premium booking's join link is an Odoo-hosted, stable URL (same
shape as Discuss's own) - the actual SignalWire room token gets
generated fresh at click time, not baked in ahead of the appointment,
since a token is a JWT that could otherwise expire before a real
booking (made days out) actually happens. The join page itself embeds
a vendored copy of SignalWire's own browser SDK.

See ``README.md`` for exactly what's live-verified here and what
isn't yet - the Video API's room/room-token layer is confirmed
working; the per-participant usage/cost data used for billing is not,
since generating it needs an actual joined WebRTC call, the one thing
that can't be driven from a script.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': [
        'telehealth_booking', 'signalwire_voip', 'signalwire_voip_sale', 'website',
    ],
    'data': [
        'data/product_telehealth_premium_data.xml',
        'views/join_templates.xml',
        'views/res_users_views.xml',
    ],
    'installable': True,
    'application': False,
}
