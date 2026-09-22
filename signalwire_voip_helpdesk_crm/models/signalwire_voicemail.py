# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import _, fields, models
from odoo.exceptions import UserError


class SignalWireVoicemail(models.Model):
    _inherit = 'signalwire.voicemail'

    helpdesk_ticket_id = fields.Many2one(
        'helpdesk.ticket', readonly=True, copy=False,
        help="Set once this voicemail has been attached to an existing "
             "ticket (see action_attach_to_ticket). \"Create Helpdesk "
             "Ticket\" opens a new, unsaved form for review instead of "
             "creating a record directly, so there's no reliable way "
             "to link that path back here the same way.")

    def _followup_description(self):
        """Markup's own %-substitution auto-escapes non-Markup operands
        (the caller number, duration, and especially the transcript -
        free-form speech-to-text output, not trusted input) - same
        idiom signalwire.voicemail._log_transcription already uses.
        """
        self.ensure_one()
        body = Markup("%s") % _(
            "Voicemail from %(number)s (%(duration)ss)",
            number=self.from_number, duration=self.duration)
        if self.transcription_text:
            body += Markup("<br/>%s") % _(
                "Transcript: %(text)s", text=self.transcription_text)
        return body

    def action_create_helpdesk_ticket(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_(
                "This voicemail's caller doesn't match a known contact, "
                "so there's no one to open a ticket against - create a "
                "lead instead."))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'helpdesk.ticket',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_partner_id': self.partner_id.id,
                'default_name': _(
                    "Voicemail from %(number)s", number=self.from_number),
                'default_description': self._followup_description(),
                'default_company_id': self.phone_number_id.company_id.id,
            },
        }

    def action_create_lead(self):
        self.ensure_one()
        context = {
            'default_name': _(
                "Voicemail from %(number)s", number=self.from_number),
            'default_description': self._followup_description(),
        }
        if self.partner_id:
            context['default_partner_id'] = self.partner_id.id
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'crm.lead',
            'view_mode': 'form',
            'target': 'current',
            'context': context,
        }

    def action_attach_to_ticket(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_(
                "This voicemail's caller doesn't match a known contact, "
                "so there are no existing tickets to attach it to."))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'signalwire.voicemail.attach.ticket.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_voicemail_id': self.id},
        }
