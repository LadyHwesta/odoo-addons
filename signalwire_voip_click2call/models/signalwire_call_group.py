# -*- coding: utf-8 -*-
from odoo import fields, models


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

    name = fields.Char(required=True)
    member_ids = fields.Many2many('res.users', string="Members")
    voicemail_user_id = fields.Many2one(
        'res.users', string="Unanswered Calls Go To",
        help="If nobody in the group answers, the call goes to this "
             "user's own voicemail box. Leave blank to just end an "
             "unanswered call with a spoken apology instead - a "
             "group has no single natural owner for a full personal "
             "fallback chain the way a directly-routed user does.")
    active = fields.Boolean(default=True)
