# Notification Emails Without Hidden Preview Text

Removes the invisible "preview" block Odoo puts at the top of every
notification email (chatter messages, followers' notifications, document
emails sent from records).

## Why this exists

Odoo 19's `mail.notification_preview` template, called at the top of both
notification layouts, is a `display: none`, 0px-font `<div>` holding a
preview of the message followed by 140 invisible padding characters
(`&#847; &#8203;`), so inbox previews show the first line only.

SpamAssassin's `FONT_INVIS_MSGID` rule fires on invisible text combined
with a random-looking Message-ID, and Odoo's Message-IDs always look random.
It costs 2.5 points (5 means spam). Found 2026-11-10 with mail-tester.com
while moving a customer's mail: SPF, DKIM, DMARC, reverse DNS and
blocklists all passed, and the score was still 6.7/10 from this alone. No
OCA module covers it (checked the same day).

## What it does

Replaces the hidden `<div>` with nothing, so the template renders empty and
the email starts with the message. Inbox previews then show the opening of
the message itself, which is what most email does anyway.

Not touched: the *preview text* field you can fill in on a mass mailing or
template (`mail.render.mixin._prepend_preview`). That is a marketing
preheader you choose to add; leave it empty if spam scores matter more.

## Install

Install, no settings. Uninstall to get Odoo's hidden preview back.
