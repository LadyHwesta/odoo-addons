# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.exceptions import UserError


class CalDAVCalendarSelect(models.TransientModel):
    _name = 'caldav.calendar.select'
    _description = 'Select a discovered CalDAV calendar'

    user_id = fields.Many2one('res.users', required=True)
    line_ids = fields.One2many('caldav.calendar.select.line', 'wizard_id')
    selected_line_id = fields.Many2one(
        'caldav.calendar.select.line', string='Calendar',
        domain="[('wizard_id', '=', id)]", required=True)

    def action_confirm(self):
        self.ensure_one()
        if not self.selected_line_id:
            raise UserError(self.env._('Please select a calendar.'))
        self.user_id.write({
            'caldav_url': self.selected_line_id.url,
            'caldav_sync_status': 'active',
        })
        return {'type': 'ir.actions.act_window_close'}


class CalDAVCalendarSelectLine(models.TransientModel):
    _name = 'caldav.calendar.select.line'
    _description = 'Discovered CalDAV calendar'

    wizard_id = fields.Many2one('caldav.calendar.select', required=True, ondelete='cascade')
    name = fields.Char(string='Calendar Name', required=True)
    url = fields.Char(required=True)
