# -*- coding: utf-8 -*-
import base64

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDMSFileOnlyoffice(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        partner_model = cls.env.ref('base.model_res_partner')
        cls.storage = cls.env['dms.storage'].create({
            'name': 'Test Attachment Storage',
            'save_type': 'attachment',
            'model_ids': [(6, 0, [partner_model.id])],
        })
        cls.directory = cls.env['dms.directory'].create({
            'name': 'Test Root Directory',
            'is_root_directory': True,
            'storage_id': cls.storage.id,
            'model_id': partner_model.id,
        })
        cls.partner = cls.env['res.partner'].create({'name': 'Test Partner'})
        cls.other_user = cls.env['res.users'].create({
            'name': 'Other User',
            'login': 'dms_onlyoffice_other_user@example.com',
        })

    def _create_dms_file(self, filename='report.docx', content=b'hello world'):
        self.env['ir.attachment'].create({
            'name': filename,
            'res_model': 'res.partner',
            'res_id': self.partner.id,
            'datas': base64.b64encode(content),
        })
        return self.env['dms.file'].search([
            ('attachment_id.res_model', '=', 'res.partner'),
            ('attachment_id.res_id', '=', self.partner.id),
            ('name', '=', filename),
        ], limit=1)

    def test_action_open_onlyoffice_editor_returns_act_url(self):
        dms_file = self._create_dms_file()

        action = dms_file.action_open_onlyoffice_editor()

        self.assertEqual(action['type'], 'ir.actions.act_url')
        self.assertEqual(
            action['url'],
            '/onlyoffice/editor/%s' % dms_file.attachment_id.id)
        self.assertEqual(action['target'], 'new')

    def test_raises_without_a_backing_attachment(self):
        database_storage = self.env['dms.storage'].create({
            'name': 'Database Storage', 'save_type': 'database',
        })
        directory = self.env['dms.directory'].create({
            'name': 'Database Directory',
            'is_root_directory': True,
            'storage_id': database_storage.id,
        })
        dms_file = self.env['dms.file'].create({
            'name': 'note.docx',
            'directory_id': directory.id,
            'content': base64.b64encode(b'hello'),
        })

        with self.assertRaises(UserError):
            dms_file.action_open_onlyoffice_editor()

    def test_raises_for_unsupported_extension(self):
        dms_file = self._create_dms_file(filename='archive.zip')

        with self.assertRaises(UserError):
            dms_file.action_open_onlyoffice_editor()

    def test_raises_when_locked_by_another_user(self):
        dms_file = self._create_dms_file()
        dms_file.locked_by = self.other_user

        with self.assertRaises(UserError):
            dms_file.action_open_onlyoffice_editor()

    def test_succeeds_when_locked_by_self(self):
        dms_file = self._create_dms_file()
        dms_file.locked_by = self.env.user

        action = dms_file.action_open_onlyoffice_editor()

        self.assertEqual(action['type'], 'ir.actions.act_url')

    def test_onlyoffice_callback_style_write_refreshes_dms_file_metadata(self):
        """Regression test for the real gap this module exists to close:
        ONLYOFFICE's own save-back callback writes straight to the
        underlying ir.attachment (attachment.write({'raw': ..})) with no
        idea dms.file even exists, which otherwise leaves dms.file's own
        checksum/size/mimetype/extension stale."""
        dms_file = self._create_dms_file(
            filename='report.docx', content=b'version one')
        stale_checksum = dms_file.checksum
        stale_size = dms_file.size

        new_content = b'version two, a good deal longer than version one'
        dms_file.attachment_id.write({
            'raw': new_content,
            'mimetype': 'text/plain',
        })

        self.assertNotEqual(dms_file.checksum, stale_checksum)
        self.assertNotEqual(dms_file.size, stale_size)
        self.assertEqual(dms_file.size, len(new_content))
        self.assertEqual(
            dms_file.checksum, dms_file._get_checksum(new_content))
