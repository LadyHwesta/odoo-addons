# Email Templates Menu

Adds a plain "Email Templates" entry under Settings - next to General
Settings, not nested under Technical - so editing an email template
doesn't require sending a customer into developer mode.

## Why this exists

Odoo's own Email Templates screen is already simple once you're on
it: the routing/context-action fields on `mail.template`'s form are
already hidden unless developer mode is on, and full edit rights are
already gated by a real, standalone permission -
`mail.group_mail_template_editor` - that has nothing to do with
developer mode.

The only actual obstacle is the menu itself. The stock menu entry
(`mail.menu_email_templates`) lives under `Settings > Technical >
Email`, and the whole Technical menu tree requires developer mode (or
a permanent "Technical feature" grant) just to be visible at all. So
a customer who should only ever manage a handful of email templates
still has to be walked through enabling developer mode first - which
also exposes them to every other Technical menu at the same time.

This module doesn't touch permissions or the underlying model at all.
It just gives the existing `mail.group_mail_template_editor`
permission a second, plain front door.

## What it does

One new menu item, "Email Templates", under Settings (sibling to
"General Settings"), pointing at Odoo's own existing Email Templates
action. It's visible to anyone who has been granted the "Mail Template
Editor" permission - nothing new to configure per-user beyond that one
existing checkbox.

## Setup

1. Install this module.
2. On the customer's own user record, go to **Access Rights > Other**
   and enable **Mail Template Editor** (a stock Odoo permission - this
   module doesn't add it, it just gives it a menu).
3. "Email Templates" now appears under Settings for that user, with no
   developer mode involved anywhere in the flow.

## Known limitations

- This only surfaces the *editing* screen. Scheduling a send doesn't
  need this module at all - any user can already click the clock icon
  in a chatter composer ("Send Later") to schedule an email, with no
  special permission required.
- Pairs well with `account_invoice_reminder` (same repo), which lets a
  non-technical user tweak the wording of automated invoice reminder
  emails through this same menu instead of hand-editing QWeb.
