# eLearning: License & Callsign Tracking

A pure-data module: installing it drops a ready-built course,
*"License & Callsign Tracking"*, into Odoo's **eLearning** app.

## What's in the course

Looking up a call sign from the FCC (callook.info), what a lookup
overwrites versus only fills in when blank, and the daily expiry-warning
sweep plus its settings. A 4-question quiz at the end.

## Access

Gated (`visibility="members"`, `enroll="invite"`); everyone in
`membership.group_membership_manager` is auto-enrolled via
`enroll_group_ids`. `club_amateur_radio` itself has no dedicated security
group (its fields are visible to any internal user) - the membership
managers group is the closest fit for "whoever actually does this job."

## Dependencies

Only `website_slides` + `club_amateur_radio`.
