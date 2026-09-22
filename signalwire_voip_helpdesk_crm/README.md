# SignalWire Voicemail to Helpdesk/CRM

Adds three actions to a `signalwire.voicemail` record (from
`signalwire_voip_click2call`), all on the voicemail's own form:

- **Create Helpdesk Ticket** and **Attach to Existing Ticket** - only
  shown when the caller matched a known contact (there's no one to
  open a ticket against otherwise, and both hide again once this
  voicemail has already been attached to one). Attaching lists that
  contact's own open tickets to pick from.
- **Create Lead/Opportunity** - available either way, matched contact
  or not.

Every action opens a **pre-filled, unsaved form for review** - a
ticket or lead's other real fields (team, category, priority) need a
human's judgment, so nothing gets silently created with guessed
values. The one exception is "Attach to Existing Ticket," which posts
the voicemail's recording + a note to the chosen ticket's chatter
immediately (there's nothing to review there - it's just logging
existing information onto an existing record), and is the only path
that can reliably set the voicemail's own `helpdesk_ticket_id` back -
"Create Helpdesk Ticket"/"Create Lead" hand off to a form the user
might edit heavily or not save at all, so there's no reliable moment
to capture a resulting record's id the same way.

## Why not Odoo's own `helpdesk` app

It's Enterprise-only - confirmed absent from a real CE install before
building anything here. [OCA's `helpdesk_mgmt`](https://github.com/OCA/helpdesk)
is the substitute: a real, actively maintained Community Edition
module (depends only on `mail`+`portal`). Not vendored into this repo
- this bridge only ever creates/reads `helpdesk.ticket`/`crm.lead`
records, never needs to patch `helpdesk_mgmt`'s own behavior, so
there's no reason to take on keeping a vendored copy in sync. Install
it from OCA's own repo (19.0 branch) alongside core `crm`.

## Not yet live-verified

Same gap as the rest of `signalwire_voip_click2call`'s voicemail
features - this hasn't been exercised against a real inbound call and
a real voicemail. The action methods themselves are tested directly
(see `tests/`).
