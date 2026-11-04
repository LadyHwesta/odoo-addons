# -*- coding: utf-8 -*-
from odoo import models

CONTENT_FIELDS = {'raw', 'datas', 'mimetype'}


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    def write(self, vals):
        res = super().write(vals)
        if not CONTENT_FIELDS & vals.keys():
            return res
        if self.env.context.get('dms_file'):
            return res
        dms_files = self.env['dms.file'].sudo().search(
            [('attachment_id', 'in', self.ids)])
        dms_files._onlyoffice_sync_from_attachment()
        return res
