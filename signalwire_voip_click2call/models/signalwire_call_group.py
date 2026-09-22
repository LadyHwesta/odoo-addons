# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SignalWireCallGroup(models.Model):
    """A reusable, named ring group - every member's softphone (and
    desk phones) rings at once on an inbound call routed here.
    Distinct from res.users.signalwire_ring_group_ids (an ad hoc
    personal fallback list one user configures for themselves) - this
    is a shared record a number's own routing, or an IVR menu option,
    can point at directly. v1 only supports "ring everyone at once",
    matching the ring-group fallback step's own existing behavior -
    sequential/round-robin ringing is a real, deliberately deferred
    enhancement, not built here.
    """
    _name = 'signalwire.call.group'
    _inherit = ['mail.thread']
    _description = 'SignalWire Call Group'
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company,
        help="Which company this group belongs to - a number can "
             "only route to a Call Group in that number's own "
             "company (enforced below), so each branch/company keeps "
             "its own independent set of groups even on a single "
             "shared SignalWire account.")
    member_ids = fields.Many2many('res.users', string="Members")
    voicemail_mode = fields.Selection(
        [('none', "End the Call"), ('user', "A Specific User's Voicemail"),
         ('group', "This Group's Own Shared Voicemail Box")],
        string="If Nobody Answers", default='none', required=True,
        help="What happens when nobody in the group picks up: just "
             "end the call with a spoken apology, send it to one "
             "specific member's own personal voicemail box, or to a "
             "shared mailbox that belongs to the group itself - any "
             "member can see and manage messages left there (posted "
             "to this group's own chatter below), unlike a personal "
             "box which is just that one user's own.")
    voicemail_user_id = fields.Many2one(
        'res.users', string="Voicemail User", check_company=True,
        help="Whose personal voicemail box unanswered calls go to - "
             "used when \"If Nobody Answers\" is set to \"A Specific "
             "User's Voicemail.\"")
    voicemail_greeting = fields.Binary(
        string="Custom Greeting Recording", attachment=True, copy=False,
        help="An uploaded audio file played to callers instead of the "
             "text-to-speech greeting below - used when \"If Nobody "
             "Answers\" is set to this group's own shared voicemail "
             "box. Leave unset to use the text greeting instead.")
    voicemail_greeting_filename = fields.Char(copy=False)
    voicemail_greeting_text = fields.Text(
        string="Greeting (spoken)",
        default=lambda self: _("Please leave a message after the tone."),
        help="Read aloud (text-to-speech) to callers when no custom "
             "greeting recording is set above.")
    active = fields.Boolean(default=True)

    @api.constrains('company_id', 'member_ids')
    def _check_member_company(self):
        for group in self:
            outside = group.member_ids.filtered(
                lambda u: group.company_id not in u.company_ids)
            if outside:
                raise ValidationError(
                    f"{', '.join(outside.mapped('name'))} "
                    f"{'is' if len(outside) == 1 else 'are'} not part of "
                    f"{group.company_id.name}, so can't be added to {group.name}.")
