# -*- coding: utf-8 -*-
{
    'name': 'Notification Emails Without Hidden Preview Text',
    'version': '19.0.1.0.0',
    'category': 'Discuss',
    'summary': "Drop the invisible preview block Odoo puts in every notification "
               "email, which spam filters score against",
    'description': """
Notification Emails Without Hidden Preview Text
================================================

Odoo's notification layout starts every chatter/notification email with a
hidden block (display:none, 0px font) holding a preview of the message
padded with 140 invisible characters. Together with Odoo's random-looking
Message-IDs, SpamAssassin scores this as a spammer trick
(FONT_INVIS_MSGID, 2.5 of the 5 points that mark mail as spam).

This module empties that block. Inbox previews then show the start of the
message itself. Mass mailings' own "preview text" field is left alone.

See ``README.md``.
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['mail'],
    'data': [
        'views/mail_templates.xml',
    ],
    'installable': True,
    'application': False,
}
