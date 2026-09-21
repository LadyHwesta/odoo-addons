# -*- coding: utf-8 -*-
from odoo import fields, models

VALID_DIGITS = [(str(d), str(d)) for d in range(10)] + [('*', '*'), ('#', '#')]


class SignalWireIvrMenu(models.Model):
    """A caller-facing "Press 1 for Sales" menu - the greeting is
    played via <Say> (text-to-speech, no audio upload in v1, matching
    the same <Say> convention already used for the voicemail
    greeting), then a single digit picks one of this menu's own
    options.
    """
    _name = 'signalwire.ivr.menu'
    _description = 'SignalWire IVR Menu'

    name = fields.Char(required=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company,
        help="Which company this menu belongs to - a number can "
             "only route to an IVR Menu in that number's own company "
             "(enforced via each option's own check_company fields), "
             "so each branch/company keeps its own independent menus "
             "even on a single shared SignalWire account.")
    greeting_text = fields.Text(
        required=True,
        help="Played (as text-to-speech) when a caller reaches this "
             "menu, before they're asked to press a digit.")
    option_ids = fields.One2many('signalwire.ivr.menu.option', 'menu_id', string="Options")
    active = fields.Boolean(default=True)


class SignalWireIvrMenuOption(models.Model):
    _name = 'signalwire.ivr.menu.option'
    _description = 'SignalWire IVR Menu Option'
    _order = 'digit'
    _check_company_auto = True

    menu_id = fields.Many2one(
        'signalwire.ivr.menu', required=True, ondelete='cascade')
    company_id = fields.Many2one(
        related='menu_id.company_id', store=True,
        help="Follows the parent menu's own company - used to keep "
             "every target below (user/group/submenu) scoped to the "
             "same company as this option's own menu.")
    digit = fields.Selection(VALID_DIGITS, required=True)
    action_type = fields.Selection(
        [('user', "Ring a User"), ('group', "Ring a Call Group"),
         ('submenu', "Go to Another Menu"), ('voicemail', "Take a Voicemail"),
         ('hangup', "Hang Up")],
        required=True, default='user')
    target_user_id = fields.Many2one(
        'res.users', string="User", check_company=True,
        help="Used when Action is \"Ring a User\" or \"Take a "
             "Voicemail\" (whose voicemail box the message goes to).")
    target_call_group_id = fields.Many2one(
        'signalwire.call.group', string="Call Group", check_company=True)
    target_submenu_id = fields.Many2one(
        'signalwire.ivr.menu', string="Menu", check_company=True,
        help="A different IVR menu to jump the caller into.")

    _menu_digit_unique = models.Constraint(
        'unique(menu_id, digit)',
        "Two options on the same menu can't share the same digit.",
    )
