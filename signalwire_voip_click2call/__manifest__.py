# -*- coding: utf-8 -*-
{
    'name': 'VoIP Click-to-Call',
    'version': '19.0.4.12.0',
    'category': 'Productivity/VOIP',
    'summary': 'An in-browser softphone, desk phones, call routing, voicemail and a receptionist panel',
    'description': """
VoIP Click-to-Call
==================

Calling from Odoo, built on OCA's ``voip_oca`` browser softphone.

- **Softphones**: one click sets up a user's softphone. Make and take
  calls in the browser, click any contact's number to call it, with a
  call log and missed-call activities.
- **Desk phones**: register Yealink or Grandstream desk phones by MAC
  address; they ring with the softphone and set themselves up
  automatically.
- **Call routing**: each number rings a user, a call group or a phone
  menu (IVR), with opening hours, after-hours routing, hold music and
  attended transfer.
- **When nobody answers**: forward to a saved number, ring teammates,
  then take a voicemail.
- **Voicemail**: a topbar inbox with playback and optional transcripts.
- **Receptionist panel**: see who's on a call and route callers.

Setup notes are in ``README.md``.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': [
        'signalwire_voip', 'voip_oca', 'phone_validation', 'mail', 'resource'],
    'data': [
        'security/signalwire_receptionist_security.xml',
        'security/ir.model.access.csv',
        'security/signalwire_voicemail_security.xml',
        'security/signalwire_call_routing_security.xml',
        'data/ir_cron.xml',
        'views/res_users_views.xml',
        'views/signalwire_voip_layout_views.xml',
        'views/signalwire_phone_number_views.xml',
        'views/signalwire_ivr_menu_views.xml',
        'views/signalwire_server_views.xml',
        'views/signalwire_voicemail_views.xml',
        'views/signalwire_receptionist_panel_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'signalwire_voip_click2call/static/src/services/voip_agent_early_media.esm.js',
            'signalwire_voip_click2call/static/src/services/voip_agent_turn.esm.js',
            'signalwire_voip_click2call/static/src/services/voip_agent_attended_transfer.esm.js',
            'signalwire_voip_click2call/static/src/services/voip_agent_receptionist_status.esm.js',
            'signalwire_voip_click2call/static/src/components/receptionist_panel/receptionist_panel.esm.js',
            'signalwire_voip_click2call/static/src/components/receptionist_panel/receptionist_panel.xml',
            'signalwire_voip_click2call/static/src/components/transfer/transfer.esm.js',
            'signalwire_voip_click2call/static/src/components/transfer/transfer.xml',
            'signalwire_voip_click2call/static/src/components/call/call.esm.js',
            'signalwire_voip_click2call/static/src/components/call/call.xml',
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
