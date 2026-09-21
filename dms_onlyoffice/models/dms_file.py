# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.onlyoffice_odoo.utils import file_utils


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
        return {
            'type': 'ir.actions.act_url',
            'url': '/onlyoffice/editor/%s' % self.attachment_id.id,
            'target': 'new',
        }
