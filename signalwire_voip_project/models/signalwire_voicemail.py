# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class SignalWireVoicemail(models.Model):
    _inherit = 'signalwire.voicemail'

    project_id = fields.Many2one(
        'project.project', readonly=True, copy=False,
        help="Set once this voicemail has been attached to an "
             "existing project (see action_attach_to_project_or_task) "
             "or promoted straight to a new task's own project via "
             "action_create_task.")
    task_id = fields.Many2one(
        'project.task', readonly=True, copy=False,
        help="Set once this voicemail has been attached to an "
             "existing task (see action_attach_to_project_or_task) - "
             "\"Create Task\" opens a new, unsaved form for review "
             "instead of creating a record directly, so there's no "
             "reliable way to link that path back here the same way.")

    @api.constrains('project_id', 'task_id')
    def _check_not_both_project_and_task(self):
        for voicemail in self:
            if voicemail.project_id and voicemail.task_id:
                raise ValidationError(_(
                    "A voicemail can be attached to a project or a "
                    "task, not both at once."))

    def _followup_description(self):
        """Duplicated from signalwire_voip_helpdesk_crm's own method
        of the same name rather than depending on that module - this
        module is meant to install on its own, and the two bridges
        (Helpdesk/CRM, Project) shouldn't need each other. Markup's
        own %-substitution auto-escapes non-Markup operands (the
        caller number, duration, and especially the transcript - free-
        form speech-to-text output, not trusted input) - same idiom
        signalwire.voicemail._log_transcription already uses.
        """
        self.ensure_one()
        body = Markup("%s") % _(
            "Voicemail from %(number)s (%(duration)ss)",
            number=self.from_number, duration=self.duration)
        if self.transcription_text:
            body += Markup("<br/>%s") % _(
                "Transcript: %(text)s", text=self.transcription_text)
        return body

    def _default_matching_project(self):
        """Fluid-flow default for action_create_task: if the matched
        contact already has exactly one project flagged as theirs,
        pre-fill it - zero or several matches leave the field blank
        for a human to pick (or create a new one via the Project
        field's own normal "Create..." option) rather than ever
        guessing which one is meant.
        """
        self.ensure_one()
        if not self.partner_id:
            return False
        projects = self.env['project.project'].search([('partner_id', '=', self.partner_id.id)])
        return projects.id if len(projects) == 1 else False

    def action_create_task(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_(
                "This voicemail's caller doesn't match a known "
                "contact, so there's no one to create a task for."))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'project.task',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_partner_id': self.partner_id.id,
                'default_project_id': self._default_matching_project(),
                'default_name': _(
                    "Voicemail from %(number)s", number=self.from_number),
                'default_description': self._followup_description(),
                'default_company_id': self.phone_number_id.company_id.id,
            },
        }

    def action_attach_to_project_or_task(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_(
                "This voicemail's caller doesn't match a known "
                "contact, so there are no existing projects or tasks "
                "to attach it to."))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'signalwire.voicemail.attach.project.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_voicemail_id': self.id},
        }
