# -*- coding: utf-8 -*-
from odoo import fields, models


class Website(models.Model):
    _inherit = 'website'

    gig_booking_team_id = fields.Many2one(
        'crm.team', string='Booking Requests Go To',
        help="The sales team (and so the company) that this website's Book a Date requests "
             "go to. Empty: the website's own lead or shop team, in the website's company.")
