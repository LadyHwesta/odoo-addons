# Project Task Contact Assignee

Adds one field, **Assigned Contact** (`assignee_partner_id`), to
`project.task` - works identically on a regular task and a subtask
(a subtask is just a task with `parent_id` set, so no special-casing
was needed).

## Why this exists

Odoo core's own Assignees field (`user_ids`) is internal staff only -
its own domain, `[('share', '=', False), ('active', '=', True)]`,
structurally excludes portal/share users. `partner_id` ("Customer")
is a single field inherited from the project/parent task, not really
an assignment mechanism. Neither lets you say "this specific *contact*
is responsible for this task."

Checked before building anything here:

- **OCA's `project` repo**, both the `18.0` and `19.0` branches
  (`gh api repos/OCA/project/contents?ref=<branch>`) - nothing does
  task-level, contact-based assignment.
- **`project_role`** (has a 19.0 branch) - project-level, and it
  assigns **`res.users`** by role, not `res.partner`.
- **`project_stakeholder`** (**18.0 only, not yet ported to 19.0**) -
  closer in spirit (adds `res.partner` stakeholders with a role), but
  it's project-level involvement tracking, not task/subtask
  assignment.
- **Core's own `project.collaborator`** - grants a partner **portal
  access** to a shared project. Access, not assignment.

Nothing existing covers this, so this module adds the one missing
field directly.

## Deliberately scoped

- **No access-control side effects.** Setting `assignee_partner_id`
  never touches `project.collaborator` and never changes what the
  assigned contact can see. It's a plain organizational field - if you
  also want the contact to have portal visibility into the task,
  that's a separate, deliberate action (Project's own sharing
  feature), not something this module does automatically. Proven, not
  just asserted - see `test_assigning_a_contact_grants_no_extra_portal_access`.
- **Single contact, not multiple** (`Many2one`, not `Many2many`) -
  matches how `partner_id` (Customer) already works, rather than
  `user_ids`' multi-assignee shape. "Who's the responsible contact for
  this task" is usually one person.
- **No domain restriction** on which contacts are selectable - any
  `res.partner`, same as `partner_id` itself.
- **Form, list, and search views only** - the field is not added to
  the kanban card template (a complex, icon/avatar-heavy XPath target
  already carrying a lot of visual logic). A kanban badge is a clean,
  low-risk follow-up if it turns out to be wanted, not core to this
  module's scope.
