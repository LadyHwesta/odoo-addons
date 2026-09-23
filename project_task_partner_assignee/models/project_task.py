# -*- coding: utf-8 -*-
from odoo import fields, models


class ProjectTask(models.Model):
    _inherit = 'project.task'

    assignee_partner_id = fields.Many2one(
        'res.partner', string="Assigned Contact", tracking=True,
        help="A specific contact responsible for this task or subtask "
             "- distinct from Assignees (internal staff, above) and "
             "Customer (who the task is for). Purely organizational: "
             "assigning a contact here does not grant them any access "
             "to see this task.")
