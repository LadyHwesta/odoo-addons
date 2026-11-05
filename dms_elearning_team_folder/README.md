# eLearning: Documents, Team Folders, and ONLYOFFICE

A pure-data module: installing it drops a ready-built course into Odoo's
**eLearning** app.

## What's in the course

Choosing where a document should live, connecting ONLYOFFICE, creating and running
team folders, scenarios for teams, committees and individuals, what team folders
can't do, linking a storage to a kind of record, and common problems. A 4-question
quiz at the end.

Screenshots in `static/img/` come from a local test database with sample data.

## Access

Gated (`visibility="members"`, `enroll="invite"`). Everyone with the Documents
**User** role is auto-enrolled, which includes anyone added to a team folder.

## Dependencies

`website_slides`, `club_elearning_theme`, `dms_team_folder`, `dms_onlyoffice`.
