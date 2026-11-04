# -*- coding: utf-8 -*-
import base64

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.mimetypes import guess_mimetype

from odoo.addons.dms.tools import file as dms_file_tools
from odoo.addons.onlyoffice_odoo.utils import config_utils, file_utils


class DMSFile(models.Model):
    _inherit = 'dms.file'

    can_edit_with_onlyoffice = fields.Boolean(
        compute='_compute_onlyoffice_capabilities')
    can_view_with_onlyoffice = fields.Boolean(
        compute='_compute_onlyoffice_capabilities')

    @api.depends('attachment_id', 'name')
    def _compute_onlyoffice_capabilities(self):
        for record in self:
            if not record.attachment_id or not record.name:
                record.can_edit_with_onlyoffice = False
                record.can_view_with_onlyoffice = False
                continue
            record.can_edit_with_onlyoffice = file_utils.can_edit(record.name)
            record.can_view_with_onlyoffice = file_utils.can_view(record.name)

    @api.model_create_multi
    def create(self, vals_list):
        # dms leaves these blank when a file's content is in an attachment,
        # so its size would show as empty until the first save.
        files = super().create(vals_list)
        files.sudo().filtered('attachment_id')._onlyoffice_sync_from_attachment()
        return files

    def _onlyoffice_sync_from_attachment(self):
        for dms_file in self:
            binary = dms_file.attachment_id.raw or b''
            mimetype = guess_mimetype(binary)
            extension = dms_file_tools.guess_extension(
                dms_file.name, mimetype, base64.b64encode(binary))
            dms_file.write({
                'checksum': dms_file._get_checksum(binary),
                'size': len(binary),
                'mimetype': mimetype,
                'extension': extension,
            })

    def action_open_onlyoffice_editor(self):
        self.ensure_one()
        if not self.attachment_id:
            raise UserError(self.env._(
                "This file's storage doesn't keep a real attachment behind "
                "it, so ONLYOFFICE has nothing to open. Only files stored "
                "on an \"Attachment\" storage can be edited in ONLYOFFICE."))
        if not self.can_view_with_onlyoffice:
            raise UserError(self.env._(
                "ONLYOFFICE doesn't support editing or viewing this file "
                "type."))
        if self.is_locked and not self.is_lock_editor:
            raise UserError(self.env._(
                "This file is locked by %s.", self.locked_by.name))
        if config_utils.get_same_tab(self.env):
            # ONLYOFFICE's own in-app editor. Stays inside the Odoo window,
            # so it also stays inside an installed PWA.
            return {
                'type': 'ir.actions.client',
                'tag': 'onlyoffice_editor',
                'target': 'current',
                'params': {'attachment_id': self.attachment_id.id},
            }
        return {
            'type': 'ir.actions.act_url',
            'url': '/onlyoffice/editor/%s' % self.attachment_id.id,
            'target': 'new',
        }
