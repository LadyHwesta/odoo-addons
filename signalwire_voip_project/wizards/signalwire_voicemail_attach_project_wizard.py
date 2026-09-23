# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class SignalWireVoicemailAttachProjectWizard(models.TransientModel):
    """Attaches a voicemail's recording + a chatter note to an
    existing project or task for the voicemail's own matched contact -
    the "attach to existing" half of this module's own voicemail
    actions, offering either target in one wizard rather than as two
    separate buttons. Both domains are narrowed to records already
    flagged for the matched contact (project.project.partner_id /
    project.task.partner_id, both core fields) - the "fluid lookup"
    this was asked for comes for free from that.
    """
    _name = 'signalwire.voicemail.attach.project.wizard'
    _description = 'Attach Voicemail to Project or Task'

    voicemail_id = fields.Many2one(
        'signalwire.voicemail', required=True, default=lambda self: self.env.context.get(
            'default_voicemail_id'))
    partner_id = fields.Many2one(related='voicemail_id.partner_id')
    attach_mode = fields.Selection(
        [('task', "Task"), ('project', "Project")],
        required=True, default='task')
    project_id = fields.Many2one(
        'project.project', domain="[('partner_id', '=', partner_id)]")
    task_id = fields.Many2one(
        'project.task', domain="[('partner_id', '=', partner_id)]")

    def action_attach(self):
        self.ensure_one()
        voicemail = self.voicemail_id
        if self.attach_mode == 'project':
            if not self.project_id:
                raise UserError(_("Pick a project to attach this voicemail to."))
            record = self.project_id
            voicemail.project_id = record.id
        else:
            if not self.task_id:
                raise UserError(_("Pick a task to attach this voicemail to."))
            record = self.task_id
            voicemail.task_id = record.id
        record.message_post(
            body=voicemail._followup_description(),
            attachment_ids=voicemail.recording_attachment_id.ids)
        return {'type': 'ir.actions.act_window_close'}
