# -*- coding: utf-8 -*-
{
    'name': 'Project Task Contact Assignee',
    'version': '19.0.1.0.0',
    'category': 'Services/Project',
    'summary': "Assign a task or subtask to a specific contact, not just internal staff",
    'description': """
Project Task Contact Assignee
====================================

Odoo's own Assignees (``user_ids``) are internal staff only - its own
domain explicitly excludes portal/share users. There's no way to mark
a specific *contact* (``res.partner``) as responsible for a task or
subtask, distinct from the task's Customer.

Checked OCA's ``project`` repo first (both the ``18.0`` and ``19.0``
branches) and core Odoo 19 directly before building this - nothing
does task-level, contact-based assignment. The closest things that
exist (``project_role``, user-based project roster; ``project_stakeholder``,
partner-based but project-level, 18.0-only; core's own
``project.collaborator``, portal *access*, not assignment) all solve a
different problem.

Adds one field, ``assignee_partner_id``, to ``project.task`` - works
identically on a top-level task and a subtask (a subtask is just a
task with ``parent_id`` set). Auto-subscribes the assigned contact as
a follower, the same way core's own Assignees (``user_ids``) already
do, so the task's own chatter can actually reach them by email. See
the README for the one real access-shape nuance that comes with that
(only relevant if the assigned contact is also a portal user).
""",
    'author': 'Tiesa',
    'license': 'LGPL-3',
    'website': 'https://github.com/LadyHwesta/odoo-addons',
    'depends': ['project'],
    'data': [
        'views/project_task_views.xml',
    ],
    'installable': True,
    'application': False,
}
