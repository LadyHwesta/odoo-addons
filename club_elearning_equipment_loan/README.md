# eLearning: Equipment Loans

A pure-data module: installing it drops a ready-built course,
*"Equipment Loans"*, into Odoo's **eLearning** app.

## What's in the course

Marking equipment loanable and the default loan length setting, the
Reserved → On Loan → Returned workflow and the borrower-acceptance gate
on checkout, and the overdue sweep plus the borrower's own `/my/loans`
portal view. A 4-question quiz at the end.

## Access

Gated (`visibility="members"`, `enroll="invite"`); everyone in
`maintenance.group_equipment_manager` is auto-enrolled via
`enroll_group_ids`.

## Dependencies

Only `website_slides` + `club_equipment_loan`.
