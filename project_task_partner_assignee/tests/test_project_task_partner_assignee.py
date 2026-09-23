# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestProjectTaskPartnerAssignee(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.contact = cls.env['res.partner'].create({'name': 'Jane Contact'})
        cls.other_contact = cls.env['res.partner'].create({'name': 'Other Contact'})
        cls.project = cls.env['project.project'].create({'name': 'Test Project'})

    def test_field_is_set_and_readable_on_a_task(self):
        task = self.env['project.task'].create({
            'name': 'Task', 'project_id': self.project.id,
            'assignee_partner_id': self.contact.id,
        })

        self.assertEqual(task.assignee_partner_id, self.contact)

    def test_field_works_independently_on_a_subtask(self):
        parent = self.env['project.task'].create({
            'name': 'Parent Task', 'project_id': self.project.id,
            'assignee_partner_id': self.contact.id,
        })
        subtask = self.env['project.task'].create({
            'name': 'Subtask', 'project_id': self.project.id,
            'parent_id': parent.id, 'assignee_partner_id': self.other_contact.id,
        })

        self.assertEqual(parent.assignee_partner_id, self.contact)
        self.assertEqual(subtask.assignee_partner_id, self.other_contact)

    def test_search_by_assignee_partner(self):
        task = self.env['project.task'].create({
            'name': 'Task', 'project_id': self.project.id,
            'assignee_partner_id': self.contact.id,
        })
        self.env['project.task'].create({
            'name': 'Unrelated Task', 'project_id': self.project.id,
        })

        found = self.env['project.task'].search([('assignee_partner_id', '=', self.contact.id)])

        self.assertEqual(found, task)

    def test_group_by_assignee_partner(self):
        self.env['project.task'].create({
            'name': 'Task 1', 'project_id': self.project.id,
            'assignee_partner_id': self.contact.id,
        })
        self.env['project.task'].create({
            'name': 'Task 2', 'project_id': self.project.id,
            'assignee_partner_id': self.contact.id,
        })
        self.env['project.task'].create({
            'name': 'Task 3', 'project_id': self.project.id,
            'assignee_partner_id': self.other_contact.id,
        })

        groups = self.env['project.task']._read_group(
            [('project_id', '=', self.project.id)],
            groupby=['assignee_partner_id'], aggregates=['__count'])
        counts = {partner.id if partner else False: count for partner, count in groups}

        self.assertEqual(counts.get(self.contact.id), 2)
        self.assertEqual(counts.get(self.other_contact.id), 1)

    def test_assigning_a_contact_subscribes_them_as_a_follower(self):
        """Being a follower is what lets the task's own chatter
        actually reach them by email (Send Message/Log Note) - the
        same mechanism Assignees (user_ids) already get for free.
        """
        task = self.env['project.task'].create({
            'name': 'Task', 'project_id': self.project.id,
            'assignee_partner_id': self.contact.id,
        })

        self.assertIn(self.contact, task.message_partner_ids)

    def test_assigning_a_contact_on_write_also_subscribes_them(self):
        task = self.env['project.task'].create({
            'name': 'Task', 'project_id': self.project.id,
        })
        self.assertNotIn(self.contact, task.message_partner_ids)

        task.write({'assignee_partner_id': self.contact.id})

        self.assertIn(self.contact, task.message_partner_ids)

    def test_assigning_a_plain_contact_grants_no_portal_login_capability(self):
        """A contact with no res.users account at all has nothing to
        log into - following the task only ever means "can be
        emailed," never "can browse into Odoo and view it."
        """
        task = self.env['project.task'].create({
            'name': 'Task', 'project_id': self.project.id,
            'assignee_partner_id': self.contact.id,
        })

        self.assertFalse(self.contact.user_ids)
        self.assertIn(self.contact, task.message_partner_ids)

    def test_assigning_a_portal_user_as_contact_does_grant_them_portal_read_access(self):
        """The one real access-shape change from auto-following:
        project's own portal sharing rule treats "is a follower" as
        one way to read a portal-shared project's task - so a contact
        who is *already* a portal user, on a project already shared
        with portal users, gains read access as a side effect of
        being assigned. A plain contact with no login (the common
        case) is entirely unaffected - see the test above.
        """
        self.project.privacy_visibility = 'portal'
        portal_partner = self.env['res.partner'].create({'name': 'Portal Jane'})
        portal_user = self.env['res.users'].create({
            'name': 'Portal Jane', 'login': 'portal.jane.assignee@example.com',
            'partner_id': portal_partner.id,
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        task = self.env['project.task'].create({
            'name': 'Task', 'project_id': self.project.id,
            'assignee_partner_id': portal_partner.id,
        })

        found = self.env['project.task'].with_user(portal_user).search([('id', '=', task.id)])

        self.assertEqual(found, task)
        self.assertEqual(
            task.with_user(portal_user).read(['name'])[0]['name'], 'Task')
