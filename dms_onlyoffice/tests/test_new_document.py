# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, new_test_user, tagged

from odoo.addons.onlyoffice_odoo.utils import file_utils


@tagged('post_install', '-at_install')
class TestNewDocument(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        partner_model = cls.env.ref('base.model_res_partner')
        cls.storage = cls.env['dms.storage'].create({
            'name': 'New Document Storage', 'save_type': 'attachment',
            'inherit_access_from_parent_record': True,
            'model_ids': [(6, 0, [partner_model.id])],
        })
        cls.root = cls.env['dms.directory'].create({
            'name': 'New Document Root', 'is_root_directory': True,
            'storage_id': cls.storage.id, 'model_id': partner_model.id,
        })
        cls.partner = cls.env['res.partner'].create({'name': 'New Document Partner'})
        cls.folder = cls.env['dms.directory'].create({
            'name': 'Linked Folder', 'parent_id': cls.root.id,
            'res_model': 'res.partner', 'res_id': cls.partner.id,
            'storage_id': cls.storage.id, 'model_id': partner_model.id,
        })
        cls.Wizard = cls.env['dms.onlyoffice.new.document']

    def _create(self, name='Notes', document_type='docx', directory=None):
        wizard = self.Wizard.create({
            'name': name, 'document_type': document_type,
            'directory_id': (directory or self.folder).id,
        })
        action = wizard.action_create()
        return action, self.env['dms.file'].search(
            [('directory_id', '=', (directory or self.folder).id)],
            order='id desc', limit=1)

    def test_every_type_creates_an_openable_file(self):
        for document_type in ('docx', 'xlsx', 'pptx', 'pdf'):
            with self.subTest(document_type=document_type):
                action, dms_file = self._create(
                    'Report ' + document_type, document_type)
                self.assertEqual(dms_file.name, 'Report %s.%s' % (document_type, document_type))
                self.assertTrue(dms_file.attachment_id)
                self.assertTrue(dms_file.can_view_with_onlyoffice)
                self.assertGreater(dms_file.size, 0)
                self.assertIn(str(dms_file.attachment_id.id), str(action))

    def test_office_types_are_editable(self):
        for document_type in ('docx', 'xlsx', 'pptx'):
            with self.subTest(document_type=document_type):
                _action, dms_file = self._create('Edit ' + document_type, document_type)
                self.assertTrue(dms_file.can_edit_with_onlyoffice)

    def test_content_is_onlyoffice_blank_template(self):
        _action, dms_file = self._create()
        self.assertEqual(
            dms_file.attachment_id.raw,
            file_utils.get_default_file_template(self.env.user.lang, 'docx'))

    def test_language_chooses_the_template(self):
        self.env.ref('base.lang_de').active = True
        self.env.user.lang = 'de_DE'
        _action, dms_file = self._create()
        self.assertEqual(
            dms_file.attachment_id.raw,
            file_utils.get_default_file_template('de_DE', 'docx'))

    def test_extension_is_not_doubled(self):
        _action, dms_file = self._create('Budget.XLSX', 'xlsx')
        self.assertEqual(dms_file.name, 'Budget.xlsx')

    def test_name_already_in_use_gets_a_number(self):
        _action, first = self._create('Same')
        _action, second = self._create('Same')
        self.assertEqual(first.name, 'Same.docx')
        self.assertNotEqual(second.name, 'Same.docx')
        self.assertTrue(second.name.endswith('.docx'))

    def test_blank_name_is_refused(self):
        with self.assertRaises(UserError):
            self._create('   ')

    def test_root_folder_is_refused_with_an_explanation(self):
        with self.assertRaises(UserError):
            self._create(directory=self.root)

    def test_folder_that_cannot_hold_it_is_not_suggested(self):
        values = self.Wizard.with_context(default_directory_id=self.root.id).default_get(
            ['directory_id'])
        self.assertNotIn('directory_id', values)
        values = self.Wizard.with_context(default_directory_id=self.folder.id).default_get(
            ['directory_id'])
        self.assertEqual(values['directory_id'], self.folder.id)

    def test_folders_are_offered_by_what_the_user_can_do(self):
        # Runs as real users, because superuser skips the folder permissions.
        domain = self.Wizard._fields['directory_id'].domain
        editor = new_test_user(
            self.env, login='new_doc_editor',
            groups='base.group_user,dms.group_dms_user,base.group_partner_manager')
        reader = new_test_user(
            self.env, login='new_doc_viewer', groups='base.group_user,dms.group_dms_user')
        Directory = self.env['dms.directory']
        offered = Directory.with_user(editor).search(domain)
        self.assertIn(self.folder, offered)
        self.assertNotIn(self.root, offered)
        self.assertNotIn(self.folder, Directory.with_user(reader).search(domain))

    def test_ordinary_user_can_create_and_open_a_document(self):
        user = new_test_user(
            self.env, login='new_doc_creator',
            groups='base.group_user,dms.group_dms_user,base.group_partner_manager')
        wizard = self.Wizard.with_user(user).create({
            'name': 'Mine', 'document_type': 'docx', 'directory_id': self.folder.id})
        action = wizard.action_create()
        dms_file = self.env['dms.file'].search([('name', '=', 'Mine.docx')])
        self.assertEqual(dms_file.create_uid, user)
        self.assertIn(str(dms_file.attachment_id.id), str(action))

    def test_only_dms_users_can_use_it(self):
        outsider = new_test_user(self.env, login='new_doc_outsider', groups='base.group_user')
        with self.assertRaises(AccessError):
            self.Wizard.with_user(outsider).create({
                'name': 'Nope', 'document_type': 'docx', 'directory_id': self.folder.id})

    def test_user_without_create_permission_on_the_folder_is_refused(self):
        user = new_test_user(self.env, login='new_doc_reader', groups='base.group_user,dms.group_dms_user')
        refused = False
        try:
            self.Wizard.with_user(user).create({
                'name': 'Nope', 'document_type': 'docx',
                'directory_id': self.folder.id}).action_create()
        except (UserError, AccessError):
            refused = True
        self.assertTrue(refused)
        self.assertFalse(self.env['dms.file'].search([('name', '=', 'Nope.docx')]))
