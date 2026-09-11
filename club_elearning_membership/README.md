# eLearning: Membership Management

A pure-data module: installing it drops a ready-built course,
*"Membership Management"*, into Odoo's **eLearning** app
(`website_slides`) - nothing to author by hand.

## What's in the course

The Annual Club Dues product and its yearly proration roll-forward, the
Club app's menus and the `/my/club` member portal, evacuation zones, and
the Member Roster / Event Statistics / Volunteer Participation / Members
Analysis reports. A 4-question quiz at the end.

## Access

Gated (`visibility="members"`, `enroll="invite"`); everyone in
`membership.group_membership_manager` is auto-enrolled via
`enroll_group_ids`.

## Dependencies

Only `website_slides` + `club_membership`.
