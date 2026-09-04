# -*- coding: utf-8 -*-
from odoo import fields, models


class EventType(models.Model):
    _inherit = 'event.type'

    activitypub_actor_id = fields.Many2one(
        'activitypub.actor', string='Federate events as',
        help='Events in this category are announced to this actor\'s '
             'Fediverse followers. Each event copies this on creation and '
             'can override it.')
