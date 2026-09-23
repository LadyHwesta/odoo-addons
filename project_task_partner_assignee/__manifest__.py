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
task with ``parent_id`` set). Deliberately has **no access-control
side effects** - it's purely an informational/organizational field;
assigning a contact does not grant them any visibility into the task.
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
