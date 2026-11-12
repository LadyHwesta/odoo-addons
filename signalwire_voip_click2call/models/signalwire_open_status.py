# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import AccessError


class SignalWireOpenStatus(models.TransientModel):
    """The day/night switch: close the phones for the rest of today (every
    number with Business Hours takes its outside-hours routing) or reopen.
    One screen, two buttons, so it's quick on a busy day."""
    _name = 'signalwire.open.status'
    _description = 'Phones Open or Closed'

    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    status = fields.Char(compute='_compute_status')
    is_closed = fields.Boolean(compute='_compute_status')
    affected_count = fields.Integer(compute='_compute_status')

    @api.depends('company_id')
    def _compute_status(self):
        Number = self.env['signalwire.phone_number']
        for wizard in self:
            until = wizard.company_id._signalwire_closed_until()
            wizard.is_closed = bool(until)
            wizard.affected_count = Number.search_count([
                ('company_id', '=', wizard.company_id.id), ('calendar_id', '!=', False)])
            if until:
                wizard.status = _("Closed early until %(until)s.",
                                  until=Number._format_local(until))
            else:
                wizard.status = _("Open as usual: calls follow each number's Business Hours.")

    def _reopen_form(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'target': 'new',
            'name': _("Phones: Open or Closed"),
            'context': {'default_company_id': self.company_id.id},
        }

    def _own_company(self):
        """Receptionists may not edit the company record itself; this one
        field is theirs to set, from this screen only, and only for a
        company they work in."""
        self.ensure_one()
        if self.company_id not in self.env.user.company_ids:
            raise AccessError(_("You can only open or close your own company's phones."))
        return self.company_id.sudo()

    def action_close_today(self):
        self._own_company().with_context(tz=self.env.user.tz).action_signalwire_close_today()
        return self._reopen_form()

    def action_reopen(self):
        self._own_company().action_signalwire_reopen()
        return self._reopen_form()
