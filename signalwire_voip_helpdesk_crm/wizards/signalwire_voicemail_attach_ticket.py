# -*- coding: utf-8 -*-
from odoo import fields, models


class SignalWireVoicemailAttachTicketWizard(models.TransientModel):
    """Attaches a voicemail's recording + a chatter note to an
    existing helpdesk ticket for the voicemail's own matched contact -
    the "attach to existing" half of this module's own voicemail
    actions. Separate from action_create_helpdesk_ticket's own "open a
    new unsaved form" flow, since attaching happens synchronously here
    and can reliably set signalwire.voicemail.helpdesk_ticket_id back,
    unlike that other flow.
    """
    _name = 'signalwire.voicemail.attach.ticket.wizard'
    _description = 'Attach Voicemail to Helpdesk Ticket'

    voicemail_id = fields.Many2one(
        'signalwire.voicemail', required=True, default=lambda self: self.env.context.get(
            'default_voicemail_id'))
    partner_id = fields.Many2one(related='voicemail_id.partner_id')
    ticket_id = fields.Many2one(
        'helpdesk.ticket', required=True,
        domain="[('partner_id', '=', partner_id), ('closed', '=', False)]")

    def action_attach(self):
        self.ensure_one()
        voicemail = self.voicemail_id
        self.ticket_id.message_post(
            body=voicemail._followup_description(),
            attachment_ids=voicemail.recording_attachment_id.ids)
        voicemail.helpdesk_ticket_id = self.ticket_id.id
        return {'type': 'ir.actions.act_window_close'}
