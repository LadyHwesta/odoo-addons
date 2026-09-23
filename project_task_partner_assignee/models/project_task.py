# -*- coding: utf-8 -*-
from odoo import fields, models


class ProjectTask(models.Model):
    _inherit = 'project.task'

    assignee_partner_id = fields.Many2one(
        'res.partner', string="Assigned Contact", tracking=True,
        help="A specific contact responsible for this task or subtask "
             "- distinct from Assignees (internal staff, above) and "
             "Customer (who the task is for). Automatically added as "
             "a follower so they can be emailed from this task's own "
             "chatter (Send Message/Log Note), the same way Assignees "
             "already are. Does not by itself grant portal login "
             "access - the only case where this changes what someone "
             "can see is a contact who is *already* a portal user on "
             "a portal-shared project, since project's own sharing "
             "rule treats \"is a follower\" as one way in.")

    def _message_auto_subscribe_followers(self, updated_values, default_subtype_ids):
        """Mirrors core's own handling of user_ids (Assignees) - being
        a follower is what lets a task's chatter actually reach
        someone by email, and Assignees already get this for free
        (see project.task's own override of this same method).
        assignee_partner_id had no equivalent, so a message sent on
        the task couldn't reach the assigned contact without manually
        adding them as a recipient every time.
        """
        followers = super()._message_auto_subscribe_followers(updated_values, default_subtype_ids)
        partner_id = updated_values.get('assignee_partner_id')
        if partner_id:
            followers.append((partner_id, default_subtype_ids, False))
        return followers
