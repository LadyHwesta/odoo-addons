# DMS Team Folders

Shared [OCA `dms`](https://github.com/OCA/dms) folders for a team or a group of
people, without tying them to a contact or other business record.

## Who can do what

| | Files in the folder | Folder settings |
|---|---|---|
| **Members** | Add, edit, delete | Read |
| **Viewers** | Read | Read |
| **Team Folder Managers** | Add, edit, delete, in every folder | Create, change, delete |
| **Everyone else** | No access | No access |

Administrators are Team Folder Managers. Adding someone to a folder also gives
them the Documents **User** role, so they can reach it. Removing them doesn't take
that role away.

## Why the access is real

An attachment's access follows the record it's linked to. Each team folder is that
record for its files, so the same rules protect the files in DMS and the attachments
behind them. Hiding a directory with DMS access groups alone wouldn't do this,
because someone could still reach the attachment through its linked record.

## Using it

1. Give whoever sets up folders the **Team Folder Manager** right, if they aren't an
   administrator.
2. Go to **Documents › Team Folders** and create one, choosing its members and viewers.
3. Open it and use the **Files** button to upload.

A folder with files can't be deleted. Archive it to hide it from the Team Folders
list, and its members and viewers can still reach the files in Documents.

## With ONLYOFFICE

Files here are stored as attachments, so if `dms_onlyoffice` is installed, they get
its **Open in ONLYOFFICE** button. Members can edit, and viewers open read-only.
