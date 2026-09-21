# -*- coding: utf-8 -*-
from odoo import api, fields, models
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
    _description = 'SignalWire Call Group'
    _check_company_auto = True

    name = fields.Char(required=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company,
        help="Which company this group belongs to - a number can "
             "only route to a Call Group in that number's own "
             "company (enforced below), so each branch/company keeps "
             "its own independent set of groups even on a single "
             "shared SignalWire account.")
    member_ids = fields.Many2many('res.users', string="Members")
    voicemail_user_id = fields.Many2one(
        'res.users', string="Unanswered Calls Go To", check_company=True,
        help="If nobody in the group answers, the call goes to this "
             "user's own voicemail box. Leave blank to just end an "
             "unanswered call with a spoken apology instead - a "
             "group has no single natural owner for a full personal "
             "fallback chain the way a directly-routed user does.")
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
