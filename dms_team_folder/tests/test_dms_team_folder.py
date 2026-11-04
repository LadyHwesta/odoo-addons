# -*- coding: utf-8 -*-
import base64

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestDmsTeamFolder(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        groups = 'base.group_user,base.group_partner_manager'
        cls.manager = new_test_user(
            cls.env, 'tf_manager', 'base.group_user,dms_team_folder.group_team_folder_manager')
        cls.member = new_test_user(cls.env, 'tf_member', groups)
        cls.viewer = new_test_user(cls.env, 'tf_viewer', groups)
        cls.outsider = new_test_user(cls.env, 'tf_outsider', groups + ',dms.group_dms_manager')
        cls.folder = cls.env['dms.team.folder'].with_user(cls.manager).create({
            'name': 'Human Resources',
            'member_ids': [(6, 0, cls.member.ids)],
            'viewer_ids': [(6, 0, cls.viewer.ids)],
        })

    def _upload(self, user=None, name='policy.docx', content=b'hello world'):
        return self.env['dms.file'].with_user(user or self.member).create({
            'name': name,
            'directory_id': self.folder.sudo().directory_id.id,
            'content': base64.b64encode(content),
        })

    def test_creating_a_folder_creates_its_directory(self):
        directory = self.folder.sudo().directory_id
        self.assertEqual(directory.name, 'Human Resources')
        self.assertEqual(directory.res_model, 'dms.team.folder')
        self.assertEqual(directory.res_id, self.folder.id)
        self.assertEqual(directory.parent_id, self.env.ref('dms_team_folder.directory_team_folders'))

    def test_members_and_viewers_get_the_documents_app(self):
        self.assertTrue(self.member.has_group('dms.group_dms_user'))
        self.assertTrue(self.viewer.has_group('dms.group_dms_user'))

    def test_renaming_a_folder_renames_its_directory(self):
        self.folder.with_user(self.manager).name = 'People Team'
        self.assertEqual(self.folder.sudo().directory_id.name, 'People Team')

    def test_only_managers_create_or_change_folders(self):
        Folder = self.env['dms.team.folder'].with_user(self.member)
        with self.assertRaises(AccessError):
            Folder.create({'name': 'Mine'})
        with self.assertRaises(AccessError):
            self.folder.with_user(self.member).write({'viewer_ids': [(4, self.outsider.id)]})
        with self.assertRaises(AccessError):
            self.folder.with_user(self.member).unlink()

    def test_administrators_are_managers(self):
        admin = new_test_user(self.env, 'tf_admin', 'base.group_system')
        self.assertTrue(admin.has_group('dms_team_folder.group_team_folder_manager'))

    def test_someone_cannot_be_both_member_and_viewer(self):
        with self.assertRaises(ValidationError):
            self.folder.with_user(self.manager).write({'viewer_ids': [(4, self.member.id)]})

    def test_member_adds_and_changes_files(self):
        dms_file = self._upload()
        self.assertEqual(dms_file.attachment_id.res_model, 'dms.team.folder')
        self.assertEqual(dms_file.attachment_id.res_id, self.folder.id)
        dms_file.attachment_id.with_user(self.member).write({'raw': b'changed'})
        dms_file.with_user(self.member).unlink()
        self.assertFalse(dms_file.exists())

    def test_viewer_can_read_but_not_change_files(self):
        dms_file = self._upload()
        as_viewer = dms_file.with_user(self.viewer)
        self.assertEqual(self.env['dms.file'].with_user(self.viewer).search_count(
            [('id', '=', dms_file.id)]), 1)
        self.assertTrue(dms_file.attachment_id.with_user(self.viewer).has_access('read'))
        self.assertFalse(dms_file.attachment_id.with_user(self.viewer).has_access('write'))
        with self.assertRaises(AccessError):
            dms_file.attachment_id.with_user(self.viewer).write({'raw': b'changed'})
        with self.assertRaises(AccessError):
            as_viewer.unlink()
        with self.assertRaises(AccessError):
            self._upload(self.viewer, 'nope.docx')

    def test_outsider_cannot_reach_files_anywhere(self):
        """Even a Documents Manager who isn't on the folder is locked out."""
        dms_file = self._upload()
        attachment = dms_file.attachment_id
        self.assertEqual(self.env['dms.file'].with_user(self.outsider).search_count(
            [('id', '=', dms_file.id)]), 0)
        self.assertEqual(self.env['dms.directory'].with_user(self.outsider).search_count(
            [('id', '=', self.folder.sudo().directory_id.id)]), 0)
        self.assertEqual(self.env['dms.team.folder'].with_user(self.outsider).search_count(
            [('id', '=', self.folder.id)]), 0)
        self.assertFalse(attachment.with_user(self.outsider).has_access('read'))
        self.assertFalse(attachment.with_user(self.outsider).has_access('write'))
        with self.assertRaises(AccessError):
            attachment.with_user(self.outsider).read(['datas'])
        with self.assertRaises(AccessError):
            attachment.with_user(self.outsider).write({'raw': b'changed'})
        with self.assertRaises(AccessError):
            self._upload(self.outsider, 'nope.docx')
        self.assertEqual(self.env['ir.attachment'].with_user(self.outsider).search_count(
            [('res_model', '=', 'dms.team.folder'), ('res_id', '=', self.folder.id)]), 0)

    def test_removing_a_member_removes_access(self):
        dms_file = self._upload()
        self.folder.with_user(self.manager).write({'member_ids': [(3, self.member.id)]})
        self.env.invalidate_all()
        attachment = dms_file.sudo().attachment_id
        self.assertFalse(attachment.with_user(self.member).has_access('read'))

    def test_folders_stay_separate(self):
        other = self.env['dms.team.folder'].with_user(self.manager).create({
            'name': 'Finance', 'member_ids': [(6, 0, self.outsider.ids)]})
        dms_file = self._upload()
        self.assertFalse(dms_file.attachment_id.with_user(self.outsider).has_access('read'))
        self.assertEqual(self.env['dms.team.folder'].with_user(self.member).search([]), self.folder)
        self.assertEqual(self.env['dms.team.folder'].with_user(self.outsider).search([]), other)

    def test_a_folder_with_files_cannot_be_deleted(self):
        self._upload()
        with self.assertRaises(UserError):
            self.folder.with_user(self.manager).unlink()

    def test_deleting_an_empty_folder_removes_its_directory(self):
        directory = self.folder.sudo().directory_id
        self.folder.with_user(self.manager).unlink()
        self.assertFalse(directory.exists())

    def test_only_managers_see_new_and_delete(self):
        Folder = self.env['dms.team.folder']
        for view_type in ('list', 'form'):
            as_manager = Folder.with_user(self.manager).get_view(view_type=view_type)['arch']
            as_member = Folder.with_user(self.member).get_view(view_type=view_type)['arch']
            self.assertIn('create="1"', as_manager, view_type)
            self.assertIn('create="0"', as_member, view_type)

    def test_files_button_opens_this_folders_files(self):
        action = self.folder.with_user(self.member).action_view_files()
        self.assertEqual(action['res_model'], 'dms.file')
        self.assertEqual(action['context']['default_directory_id'], self.folder.sudo().directory_id.id)
