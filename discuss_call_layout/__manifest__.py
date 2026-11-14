# -*- coding: utf-8 -*-
{
    'name': 'Video Call Gallery and Speaker View',
    'version': '19.0.1.0.0',
    'category': 'Productivity/Discuss',
    'summary': 'Gallery / Speaker view switch for Discuss video calls, like Zoom and Teams',
    'description': """
Video Call Gallery and Speaker View
===================================

Discuss video calls get the two views people know from Zoom and Teams:

- **Gallery view** (the default): everyone tiled.
- **Speaker view**: whoever is talking fills the screen.

A button in the call's controls switches between them, and each person's
choice is remembered on their device.

A shared screen still fills the screen while it's on. When the share ends, the
call goes back to the chosen view. Before, it stayed on the presenter's camera
and then followed whoever spoke, and the only way back to the tiles was
clicking the big video. Clicking someone's video still pins them, as before;
click it again to unpin.

Works for guests who join from a meeting invitation link too.
""",
    'author': 'Meskis Works',
    'website': 'https://meskis.net',
    'license': 'LGPL-3',
    'depends': ['mail'],
    'assets': {
        'web.assets_backend': ['discuss_call_layout/static/src/**/*'],
        'mail.assets_public': ['discuss_call_layout/static/src/**/*'],
    },
    'installable': True,
}
