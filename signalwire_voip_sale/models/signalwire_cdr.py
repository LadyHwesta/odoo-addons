# -*- coding: utf-8 -*-
from odoo import fields, models


class SignalWireCdr(models.Model):
    """One Call Detail Record - a single call or SMS pulled from
    SignalWire, priced with this project's own markup applied
    per-record (not just once over a lump sum), so a real per-record
    "rate" can be shown on a customer's phone bill - see the
    contract.line and account.move overrides in this module for how
    these get created, billed, and attached to an invoice.
    """
    _name = 'signalwire.cdr'
    _description = 'SignalWire Call Detail Record'
    _order = 'date desc'
    _rec_name = 'sid'

    subproject_id = fields.Many2one(
        'signalwire.subproject', required=True, ondelete='cascade')
    sid = fields.Char(
        string="SID", required=True, index=True,
        help="SignalWire's own ID for this call or message - the "
             "uniqueness constraint on this is what stops a record "
             "from ever being pulled, and so billed, twice.")
    record_type = fields.Selection(
        [('call', 'Call'), ('sms', 'SMS')], required=True)
    date = fields.Datetime(required=True)
    from_number = fields.Char()
    to_number = fields.Char()
    duration = fields.Integer(
        help="Seconds - calls only, always 0 for SMS.")
    wholesale_cost = fields.Float(
        help="SignalWire's own real cost for this one record, before "
             "markup - not what the customer sees anywhere.")
    rate = fields.Float(
        help="The customer-facing per-unit rate actually billed - "
             "dollars per minute for a call, a flat per-message rate "
             "for SMS. Deliberately NOT SignalWire's own wholesale "
             "rate: this is wholesale_cost with markup already "
             "applied, expressed per unit, matching what a real phone "
             "bill's own \"rate\" column means to a customer reading "
             "it - what *they* were charged, not what it cost you.")
    billed_amount = fields.Float(
        help="What the customer is actually charged for this one "
             "record - wholesale_cost with markup applied. Summed "
             "across a billing period, this is exactly the metered "
             "contract line's own price_unit for that invoice.")
    contract_line_id = fields.Many2one(
        'contract.line',
        help="Which metered contract line this record bills against - "
             "set the moment it's pulled from SignalWire, well before "
             "the actual invoice exists yet.")
    move_line_id = fields.Many2one(
        'account.move.line', readonly=True, copy=False,
        help="Set once this record's invoice actually gets created - "
             "blank means it's been priced into a pending line but not "
             "invoiced yet.")
    move_id = fields.Many2one(
        related='move_line_id.move_id', store=True, string="Invoice")

    _sid_uniq = models.Constraint(
        'unique(sid)', "This call or message has already been pulled.")
