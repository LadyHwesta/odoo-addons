# -*- coding: utf-8 -*-
{
    'name': 'SignalWire Click-to-Call',
    'version': '19.0.4.4.0',
    'category': 'Productivity/VOIP',
    'summary': 'A real in-browser softphone (voip_oca) backed by SignalWire SIP Endpoints, with fallback routing',
    'description': """
SignalWire Click-to-Call
=========================

Phase 2 of the SignalWire VoIP project. Bridges OCA's ``voip_oca`` (a
free, provider-agnostic SIP.js/WebRTC browser softphone) to SignalWire:

- One click provisions a user's own SignalWire "SIP Endpoint" and
  wires it into ``voip_oca``'s ``res.users`` VOIP settings - after
  that, that user has a real softphone (make/receive calls, click any
  partner's phone number, call log, missed-call activities) with no
  further setup.
- Assigning a purchased ``signalwire.phone_number`` to a user routes
  inbound calls to that number straight to their softphone, via a
  standard Twilio-compatible cXML ``<Dial><Sip>`` webhook.
- **A self-service fallback chain** for when nobody's at the
  softphone: forward to a saved personal number, ring a group of
  teammates, and/or take a voicemail - each independently toggleable,
  on the fly, from the user's own Preferences. See ``README.md`` for
  the full design (SignalWire has no presence/registration API at
  all, confirmed - a timeout-then-fallback chain is the only real
  mechanism available) and what's been live-verified vs. not.
- **A real voicemail box in the backend**, not just a chatter
  message and an activity: a topbar systray icon with a live unread
  badge (updates instantly over the bus, not on a timer) whose
  dropdown lets you play, read a transcript snippet, or open any
  recent voicemail without leaving your screen; a full Voicemail list
  with inline playback, transcript, mark read/unread, and delete -
  scoped so a plain user only ever sees their own. Optional per-user
  SignalWire transcription (their own paid add-on, on by default, one
  toggle to turn off) means you can often tell what a voicemail says
  before ever pressing play.
- **Hardware desk phone support**, for teams who want a real phone at
  their desk alongside (or instead of) the browser softphone. A user
  can register any number of Yealink or Grandstream desk phones by
  MAC address; each gets its own SignalWire SIP Endpoint and rings
  together with the softphone on every inbound call. Zero-touch
  auto-provisioning is built in - point the phone (or a DHCP scope's
  option 66) at this module's own provisioning URL and it fetches its
  SIP credentials automatically, no manual entry needed. See
  ``README.md`` for what's been live-verified vs. not.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['signalwire_voip', 'voip_oca', 'phone_validation'],
    'data': [
        'security/ir.model.access.csv',
        'security/signalwire_voicemail_security.xml',
        'views/res_users_views.xml',
        'views/signalwire_phone_number_views.xml',
        'views/signalwire_server_views.xml',
        'views/signalwire_voicemail_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'signalwire_voip_click2call/static/src/services/voip_agent_turn.esm.js',
            'signalwire_voip_click2call/static/src/fields/phone_field/phone_field.esm.js',
            'signalwire_voip_click2call/static/src/components/voicemail_audio_player/voicemail_audio_player.esm.js',
            'signalwire_voip_click2call/static/src/components/voicemail_audio_player/voicemail_audio_player.xml',
            'signalwire_voip_click2call/static/src/fields/voicemail_player_field/voicemail_player_field.esm.js',
            'signalwire_voip_click2call/static/src/fields/voicemail_player_field/voicemail_player_field.xml',
            'signalwire_voip_click2call/static/src/services/signalwire_voicemail_service.esm.js',
            'signalwire_voip_click2call/static/src/components/voicemail_systray/voicemail_systray.esm.js',
            'signalwire_voip_click2call/static/src/components/voicemail_systray/voicemail_systray.xml',
        ],
    },
    'installable': True,
    'application': False,
}
