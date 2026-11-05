# -*- coding: utf-8 -*-
import base64

from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.dms.tools import file as dms_file_tools
from odoo.addons.onlyoffice_odoo.utils import file_utils

# A file on Attachment storage attaches to its folder's linked record, so a
# folder without one (a root folder) can't hold a file.
DIRECTORY_DOMAIN = [
    ('storage_id.save_type', '=', 'attachment'),
    ('res_id', '>', 0),
    ('permission_create', '=', True),
]


class DmsOnlyofficeNewDocument(models.TransientModel):
    _name = 'dms.onlyoffice.new.document'
    _description = 'New ONLYOFFICE Document'

    name = fields.Char(required=True)
    document_type = fields.Selection(
        [('docx', 'Document'), ('xlsx', 'Spreadsheet'),
         ('pptx', 'Presentation'), ('pdf', 'PDF Form')],
        string='Type', required=True, default='docx')
    directory_id = fields.Many2one(
        'dms.directory', string='Folder', required=True,
        domain=DIRECTORY_DOMAIN)

    @api.model
    def default_get(self, fields_list):
        # The folder selected in Files is only a suggestion. It might be one
        # that can't hold this kind of file.
        values = super().default_get(fields_list)
        directory = values.get('directory_id')
        if directory and not self.env['dms.directory'].search_count(
                [('id', '=', directory)] + DIRECTORY_DOMAIN):
            values.pop('directory_id')
        return values

    def _file_name(self):
        self.ensure_one()
        stem = self.name.strip()
        suffix = '.%s' % self.document_type
        if stem.lower().endswith(suffix):
            stem = stem[:-len(suffix)].strip()
        if not stem:
            raise UserError(self.env._("Enter a name for the document."))
        taken = self.directory_id.sudo().file_ids.mapped('name')
        return dms_file_tools.unique_name(
            stem + suffix, taken, self.document_type)

    def action_create(self):
        self.ensure_one()
        if not self.env['dms.directory'].search_count(
                [('id', '=', self.directory_id.id)] + DIRECTORY_DOMAIN):
            raise UserError(self.env._(
                "%s can't hold new documents. Choose a folder on Attachment "
                "storage that's linked to a record and that you can add "
                "files to.", self.directory_id.display_name))
        template = file_utils.get_default_file_template(
            self.env.user.lang or 'default', self.document_type)
        dms_file = self.env['dms.file'].create({
            'name': self._file_name(),
            'directory_id': self.directory_id.id,
            'content': base64.b64encode(template),
        })
        return dms_file.action_open_onlyoffice_editor()
