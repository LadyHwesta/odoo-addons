# SignalWire Voicemail to Project

Adds two actions to a `signalwire.voicemail` record (from
`signalwire_voip_click2call`), both on the voicemail's own form:

- **Create Task** - only shown when the caller matched a known
  contact (there's no one to create a task for otherwise, and it
  hides again once this voicemail has already been attached to a
  project or task). Opens a **pre-filled, unsaved `project.task`
  form** for review - name, customer, and description are filled in,
  but a human still confirms/edits before saving. If the matched
  contact already has **exactly one** project flagged as theirs
  (`project.project.partner_id`), that project is pre-filled too;
  zero or several matches leave the Project field blank for a human
  to pick (or type a new project name - the field's own standard
  "Create..." option covers "no project exists yet" for free).
- **Attach to Project or Task** - one wizard, a toggle between the
  two. Both the Project and Task pickers are narrowed to records
  already flagged for the matched contact
  (`project.project.partner_id` / `project.task.partner_id`, both
  core fields - no custom lookup logic needed). Posts the voicemail's
  recording + a chatter note **immediately** - there's nothing to
  review there, it's just logging existing information onto an
  existing record - and is the only path that can reliably set the
  voicemail's own `project_id`/`task_id` back ("Create Task" hands
  off to a form the user might edit heavily or not save at all, so
  there's no reliable moment to capture a resulting record's id the
  same way - same reasoning `signalwire_voip_helpdesk_crm`'s own
  ticket actions already document).

A voicemail can be attached to a project **or** a task, never both at
once (enforced by a constraint) - and never both at all until you
actually attach it to one.

## Deliberately standalone

Depends only on `signalwire_voip_click2call` and core `project`, not
on `signalwire_voip_helpdesk_crm` - Project support installs on its
own. The two bridges duplicate one small helper
(`_followup_description()`) rather than depending on each other, same
"small duplicated helper, cross-referenced by comment" precedent
already used elsewhere in this project (e.g. between
`signalwire_voip_click2call` and `signalwire_voip_piper_tts`).

## Not yet live-verified

Same gap as the rest of `signalwire_voip_click2call`'s voicemail
features - this hasn't been exercised against a real inbound call and
a real voicemail. The action methods and the wizard are tested
directly (see `tests/`).
