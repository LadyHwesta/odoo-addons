# -*- coding: utf-8 -*-
{
    'name': 'VoIP Natural Voices',
    'version': '19.0.1.1.0',
    'category': 'Productivity/VOIP',
    'summary': "Natural-sounding, open-source, self-hosted voices for IVR menus and voicemail greetings",
    'description': """
VoIP Natural Voices
===================

Replaces the robotic default voice on phone menu (IVR) and voicemail
greetings with natural-sounding voices from
`Piper <https://github.com/OHF-Voice/piper1-gpl>`_, an open-source
text-to-speech engine you host yourself.

Two voices are offered, each license-checked for commercial use:

- ``ljspeech``: public domain.
- ``libritts_r``: CC BY 4.0 (commercial use permitted, attribution
  required).

Greetings are synthesized when they're saved, never during a call; a
call falls back to the built-in voice if the voice server can't be
reached. Setup and licensing notes are in ``README.md``.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['signalwire_voip_click2call'],
    'data': [
        'security/ir.model.access.csv',
        'views/signalwire_server_views.xml',
        'views/signalwire_ivr_menu_views.xml',
        'views/res_users_views.xml',
        'views/signalwire_call_group_views.xml',
        'views/signalwire_phone_number_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'signalwire_voip_piper_tts/static/src/components/piper_preview/piper_preview.esm.js',
            'signalwire_voip_piper_tts/static/src/components/piper_preview/piper_preview.xml',
        ],
    },
    'installable': True,
    'application': False,
}
