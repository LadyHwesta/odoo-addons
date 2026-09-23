# -*- coding: utf-8 -*-
{
    'name': 'SignalWire Piper TTS',
    'version': '19.0.1.0.0',
    'category': 'Productivity/VOIP',
    'summary': "Natural-sounding, open-source, self-hosted voices for IVR menus and voicemail greetings",
    'description': """
SignalWire Piper TTS
====================================

Replaces the robotic default voice on IVR menu greetings and
voicemail greetings with a genuinely open-source, self-hosted TTS
engine (`Piper <https://github.com/OHF-Voice/piper1-gpl>`_), instead
of SignalWire's own paid Amazon Polly/Google Cloud/etc. voices.

Scoped to two voices, deliberately - both individually license-
checked as safe for commercial use (Piper's own catalog is large, but
licensing is per-voice, not blanket, and some real voices - including
Piper's own documented example - explicitly prohibit commercial use):

- ``ljspeech`` - public domain, one voice.
- ``libritts_r`` - CC BY 4.0 (commercial use permitted, attribution
  required), 904 speakers (default speaker only, this version).

Synthesis happens eagerly when a greeting's text or voice is saved,
never during a live call - a real inbound call only ever plays
already-cached audio, or falls back to the plain built-in voice if
Piper isn't configured or reachable. See the README for setup and the
full licensing writeup.
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
