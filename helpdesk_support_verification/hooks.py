# -*- coding: utf-8 -*-

# Stages a ticket may reach before the customer is verified: the first
# stage, and closing it without help (cancelled or declined).
OPEN_STAGES = (
    'helpdesk_mgmt.helpdesk_ticket_stage_new',
    'helpdesk_mgmt.helpdesk_ticket_stage_cancelled',
    'helpdesk_mgmt.helpdesk_ticket_stage_rejected',
)


def post_init_hook(env):
    for xmlid in OPEN_STAGES:
        stage = env.ref(xmlid, raise_if_not_found=False)
        if stage:
            stage.requires_verification = False
    # Tickets already open were handled before verification existed: don't
    # block them halfway.
    env['helpdesk.ticket'].with_context(active_test=False).search([]).write({
        'verification_state': 'verified', 'verification_method': 'existing'})
