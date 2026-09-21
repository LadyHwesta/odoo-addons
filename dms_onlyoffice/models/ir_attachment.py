# -*- coding: utf-8 -*-
import base64

from odoo import models
from odoo.tools.mimetypes import guess_mimetype

from odoo.addons.dms.tools import file as dms_file_tools

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
        for dms_file in dms_files:
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
        return res
