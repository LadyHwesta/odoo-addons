# -*- coding: utf-8 -*-
from odoo import fields, models

from odoo.addons.base.models.res_partner import _tz_get


class ResCompany(models.Model):
    _inherit = 'res.company'

    gig_buffer_hours = fields.Float(
        string="Gap Between Gigs (hours)", default=2.0,
        help="Two bookings closer than this (setup, travel, pack-down) count as "
             "a double booking.")
    gig_balance_days = fields.Integer(
        string="Invoice Balance Before (days)", default=14,
        help="A to-do to invoice what's left is created this many days before each gig.")
    gig_min_hours = fields.Float(
        string="Minimum Hours", default=0.0,
        help="Hourly gig products never bill fewer hours than this.")
    gig_tz = fields.Selection(
        _tz_get, string="Gig Time Zone",
        help="Gig start and end times are in this time zone (usually where you play). "
             "Empty: the company's own time zone.")

    def _gig_tz(self):
        self.ensure_one()
        return self.gig_tz or self.partner_id.tz or 'UTC'
