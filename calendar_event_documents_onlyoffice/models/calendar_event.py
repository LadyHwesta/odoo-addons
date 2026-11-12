# -*- coding: utf-8 -*-
import base64

from odoo import _, fields, models
from odoo.exceptions import UserError

from odoo.addons.onlyoffice_odoo.utils import config_utils, file_utils


def _open_in_onlyoffice(attachment):
    """The action that opens an attachment in ONLYOFFICE, the same way the
    attachment buttons do: in the Odoo window or a new tab, per settings."""
    if config_utils.get_same_tab(attachment.env):
        return {
            'type': 'ir.actions.client',
            'tag': 'onlyoffice_editor',
            'target': 'current',
            'params': {'attachment_id': attachment.id},
        }
    return {
        'type': 'ir.actions.act_url',
        'url': '/onlyoffice/editor/%s' % attachment.id,
        'target': 'new',
    }


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    calendar_can_open_onlyoffice = fields.Boolean(compute='_compute_calendar_can_open_onlyoffice')

    def _compute_calendar_can_open_onlyoffice(self):
        for attachment in self:
            name = attachment.name or ''
            attachment.calendar_can_open_onlyoffice = bool(
                name and (file_utils.can_view(name) or file_utils.can_edit(name)))

    def action_calendar_open_onlyoffice(self):
        self.ensure_one()
        if not self.calendar_can_open_onlyoffice:
            raise UserError(_("ONLYOFFICE can't open this kind of file."))
        return _open_in_onlyoffice(self)


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    def _new_meeting_document(self, label):
        self.ensure_one()
        template = file_utils.get_default_file_template(self.env.user.lang or 'default', 'docx')
        name = '%s - %s.docx' % (label, self.name or _("Meeting"))
        document = self.env['ir.attachment'].create({
            'name': name.replace('/', '-'),
            'datas': base64.b64encode(template),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        })
        self.document_ids = [(4, document.id)]
        return _open_in_onlyoffice(document)

    def action_new_agenda(self):
        return self._new_meeting_document(_("Agenda"))

    def action_new_minutes(self):
        return self._new_meeting_document(_("Minutes"))
