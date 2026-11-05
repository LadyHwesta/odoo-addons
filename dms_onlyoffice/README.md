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
  It opens ONLYOFFICE's own editor for that file in a new tab, or inside Odoo
  if the same-tab setting is on
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

## Creating documents

**New Document** on the Files screen, and on a folder's form, asks for a name,
type and folder. It creates the file from ONLYOFFICE's blank template in the
user's language, then opens it in the editor. Types are Document, Spreadsheet,
Presentation and PDF Form. The folder selected in Files is filled in when it can
hold the file. A name already in use in that folder gets a number added.

Only folders on Attachment storage that are linked to a record, and that the user
can add files to, are offered. Root folders of an Attachment storage aren't linked
to a record, so they can't hold files.

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

## Verified against a real server

Tested end to end with `onlyoffice_odoo` 6.4.0 and ONLYOFFICE Docs 10.0.0: a
document opened from `dms.file`, was edited, and saved back, and `dms.file`'s
size and checksum matched the attachment afterward.

## Setting up a storage

1. On the storage, set **Save Type** to Attachment and add the existing model
   you want files attached to under **Linked Models** (for example, **Contact**).
   Don't use "Create" in these model fields, because it adds a new, empty
   database model.
2. Create a root directory with that storage, and choose the same model under
   **Model**. The list only offers the storage's linked models, so it's empty if
   step 1 was skipped.
3. Attach a file to a record of that model. Turn on **Create files from message
   attachments** on the storage to include files attached through the chatter.

**Choose linked models carefully.** DMS captures every attachment on a linked
model, including images Odoo generates. Linking Contacts, for example, also adds
contact photos as files. Deleting one of those files deletes the attachment behind
it too, so it can remove the photo. For shared documents, `dms_team_folder` avoids
this.

Attachment storage inherits access from the linked record, so DMS access groups
don't apply, and the directory form has no **Groups** tab. Creating the root
directory also requires permission to create records of the linked model.

## Staying inside the Odoo window or PWA

By default, the editor opens in a new tab, which leaves an installed PWA. To keep
it inside Odoo, turn on **Open file in the same tab** in the ONLYOFFICE settings.
In this mode, this module also makes sure someone who can only read a record opens
it read-only.

## Shared folders for a team

For folders that aren't tied to a contact or other record, use `dms_team_folder`.
Its files get the same **Open in ONLYOFFICE** button.
