# ONLYOFFICE for DMS

Bridges [ONLYOFFICE](https://www.onlyoffice.com/)'s own generic
document-editing engine (the `onlyoffice_odoo` addon) to
[OCA's `dms`](https://github.com/OCA/dms) module, so files stored in `dms`
can be opened, edited, and co-authored in ONLYOFFICE Docs.

## Why this exists

ONLYOFFICE already ships a ready-made bridge, `onlyoffice_odoo_documents`,
but it only works with Odoo's **Enterprise-only** `documents` app. There is
no equivalent for Community Edition. `onlyoffice_odoo`'s own editor engine
(the routes that open, serve, and save documents) is actually generic - it
operates on any `ir.attachment` by id, with no real dependency on
`documents` at all. This module is the missing piece: it adds an "Open in
ONLYOFFICE" action to `dms.file` records, and fixes a real gap in how the
two projects otherwise interact (see below).

## Prerequisites

1. **A running ONLYOFFICE Docs server**, reachable from your Odoo server -
   self-hosted (see ONLYOFFICE's own
   [Docker install docs](https://helpcenter.onlyoffice.com/docs/installation/docs-community-install-docker.aspx))
   or their commercial cloud offering. This module doesn't provision or
   configure that server - it's a prerequisite, the same as it would be for
   any ONLYOFFICE integration.
2. **`onlyoffice_odoo`** installed from
   [ONLYOFFICE's own repository](https://github.com/ONLYOFFICE/onlyoffice_odoo)
   (branch matching your Odoo version) and configured in Settings with your
   Docs server's URL and JWT secret. This module depends on it but
   deliberately does not vendor a copy - `onlyoffice_odoo` is ONLYOFFICE's
   own actively-versioned product, and keeping it in sync with their
   releases is better left to them.
3. **[OCA `dms`](https://github.com/OCA/dms)** installed.

## What it does

- Adds an "Open in ONLYOFFICE" button to `dms.file`'s form view (next to
  the existing Lock/Unlock buttons) and its kanban card's Actions menu.
  It opens ONLYOFFICE's own editor for that file in a new tab
  (`/onlyoffice/editor/<attachment_id>`) - `onlyoffice_odoo` itself decides
  edit vs. view-only mode based on the current user's write access to the
  underlying attachment.
- Keeps `dms.file`'s own `checksum`, `size`, `mimetype`, and `extension`
  fields in sync after ONLYOFFICE saves a document back. Without this,
  they go stale: ONLYOFFICE's save-back callback writes directly to the
  underlying `ir.attachment` (`attachment.write({'raw': ...})`) with no
  idea `dms` exists, and `dms.file`'s own fields are only ever refreshed
  through `dms.file`'s *own* content setter - never through direct writes
  to the attachment behind it. Anyone editing a `dms.file`'s attachment
  from outside `dms.file` itself hits this same gap; this module closes it
  for the ONLYOFFICE path.

## Scope limitation: attachment-backed storage only

`dms.storage` has three save types - Database, File, and Attachment. Only
the last one keeps a real `ir.attachment` behind each `dms.file`
(`dms.file.attachment_id`), which is what ONLYOFFICE's editor actually
opens. For Database/File storage, a `dms.file`'s content lives directly on
the record itself with no backing attachment at all, so there's nothing for
ONLYOFFICE to point at.

**If you want ONLYOFFICE editing on a folder, that folder's storage must be
configured with save type "Attachment."** The "Open in ONLYOFFICE" action
is hidden (and raises a clear error if called directly) for files on
Database/File storage.

## Not yet verified

This module's automated tests pass locally, but it hasn't been exercised
against a real, running ONLYOFFICE Docs server - that needs an actual
deployment, which is outside the scope of a generic, install-anywhere
module. If you hit an issue running it against a real server, please open
one.
