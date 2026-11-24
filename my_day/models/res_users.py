# -*- coding: utf-8 -*-
from odoo import api, fields, models

# Built-in backgrounds, in static/src/img/bg_<key>.jpg.
BACKGROUNDS = [
    ('dawn', "Dawn"), ('meadow', "Meadow"), ('lagoon', "Lagoon"),
    ('dusk', "Dusk"), ('aurora', "Aurora"), ('dunes', "Dunes"),
]


class ResUsers(models.Model):
    _inherit = 'res.users'

    my_day_home = fields.Boolean(
        string="Start on My Day", compute='_compute_my_day_home', inverse='_inverse_my_day_home',
        help="Open My Day after logging in.")
    my_day_background = fields.Selection(
        [('none', "None")] + BACKGROUNDS + [('custom', "My own picture")],
        string="My Day Background", default='none', required=True)
    my_day_background_image = fields.Image(
        string="My Day Picture", max_width=2560, max_height=1600, attachment=True,
        help="Your own picture for My Day's background.")

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['my_day_home', 'my_day_background', 'my_day_background_image']

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['my_day_home', 'my_day_background', 'my_day_background_image']

    def _my_day_action(self):
        """My Day as Home Action takes it: the generic action model."""
        action = self.env.ref('my_day.action_my_day', raise_if_not_found=False)
        return self.env['ir.actions.actions'].browse(action.id) if action else self.env['ir.actions.actions']

    @api.depends('action_id')
    def _compute_my_day_home(self):
        action = self._my_day_action()
        for user in self:
            user.my_day_home = bool(action) and user.action_id == action

    def _inverse_my_day_home(self):
        action = self._my_day_action()
        for user in self.sudo():
            if user.my_day_home:
                user.action_id = action
            elif action and user.action_id == action:
                user.action_id = False

    @api.model
    def _my_day_backgrounds(self):
        """The built-in backgrounds, for the picker."""
        labels = dict(self._fields['my_day_background']._description_selection(self.env))
        return [{'key': key, 'label': labels[key], 'url': f'/my_day/static/src/img/bg_{key}.jpg'}
                for key, _label in BACKGROUNDS]

    def _my_day_background_url(self):
        self.ensure_one()
        user = self.sudo()
        key = user.my_day_background
        if key == 'custom':
            if not user.my_day_background_image:
                return ''
            unique = fields.Datetime.to_string(user.write_date).replace(' ', '').replace(':', '').replace('-', '')
            return f'/web/image/res.users/{user.id}/my_day_background_image?unique={unique}'
        if key in dict(BACKGROUNDS):
            return f'/my_day/static/src/img/bg_{key}.jpg'
        return ''
