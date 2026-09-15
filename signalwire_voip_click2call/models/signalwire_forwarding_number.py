# -*- coding: utf-8 -*-
from odoo import fields, models


class SignalWireForwardingNumber(models.Model):
    """One of a user's own saved "forward my calls here" numbers - a
    small address book rather than a single field, so someone can save
    a cell and a home number and switch which one's active without
    retyping it each time (e.g. stepping away from the desk today vs.
    working from home tomorrow).
    """
    _name = 'signalwire.forwarding.number'
    _description = 'SignalWire Forwarding Number'
    _order = 'name'

    user_id = fields.Many2one('res.users', required=True, ondelete='cascade')
    name = fields.Char(required=True, help='e.g. "Cell", "Home"')
    phone_number = fields.Char(required=True, help="E.164 format.")
