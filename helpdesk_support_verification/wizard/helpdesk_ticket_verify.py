# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HelpdeskTicketVerify(models.TransientModel):
    _name = 'helpdesk.ticket.verify'
    _description = 'Verify a Helpdesk Customer'

    ticket_id = fields.Many2one('helpdesk.ticket', required=True, ondelete='cascade')
    partner_id = fields.Many2one(related='ticket_id.partner_id', string='Customer')
    code = fields.Char(string='Key or Code', help="The support key or texted code the customer reads to you.")
    can_text = fields.Boolean(compute='_compute_can_text')
    text_destination = fields.Char(compute='_compute_can_text', string='Texts Go To')
    sent_note = fields.Char(readonly=True)

    @api.depends('ticket_id', 'ticket_id.partner_id')
    def _compute_can_text(self):
        for wizard in self:
            number = wizard.ticket_id._verification_sms_number() if wizard.ticket_id else ''
            wizard.can_text = bool(number)
            wizard.text_destination = ('•••• ' + number[-4:]) if number else ''

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
            'view_mode': 'form', 'target': 'new', 'name': _('Verify Customer'),
        }

    def action_verify(self):
        self.ensure_one()
        if not self.code:
            raise UserError(_("Type the key or code the customer reads to you."))
        if not self.ticket_id._verify_with_code(self.code):
            self.code = False
            self.sent_note = _("That code didn't match. Check it with the customer, or send a new one.")
            return self._reopen()
        return {'type': 'ir.actions.act_window_close'}

    def action_send_text(self):
        self.ensure_one()
        self.ticket_id._send_verification_sms()
        self.sent_note = _("A code was texted to %(number)s. It works for 10 minutes.",
                           number=self.text_destination)
        return self._reopen()
