# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

# What a person may change on their own rows. The rest (which section, whose,
# what options it has) is set by My Day itself.
USER_FIELDS = {'sequence', 'column', 'visible', 'limit', 'days', 'include_team'}


class MyDaySectionSetting(models.Model):
    """One section of one person's My Day: shown or not, where, how many items,
    and the options that section has. Rows are created for every section the
    person can see (My Day > Preferences), so each choice is theirs."""
    _name = 'my.day.section.setting'
    _description = 'My Day Section'
    _order = 'sequence, id'

    user_id = fields.Many2one('res.users', required=True, ondelete='cascade', index=True)
    key = fields.Char(required=True, readonly=True)
    name = fields.Char(string="Section", readonly=True)
    sequence = fields.Integer(default=10)
    column = fields.Selection(
        [('plan', "Plan the day"), ('attention', "Needs attention")],
        required=True, default='attention',
        help="Plan the day is the left column, Needs attention the right.")
    visible = fields.Boolean(string="Show", default=True)
    limit = fields.Integer(string="Items", default=8, help="How many items to list (1-30).")
    days = fields.Integer(string="Days ahead", help="How far ahead this section looks.")
    has_days = fields.Boolean(readonly=True)
    days_label = fields.Char(readonly=True)
    include_team = fields.Boolean(string="Team items", default=True)
    has_team = fields.Boolean(readonly=True)
    team_label = fields.Char(readonly=True)
    option_help = fields.Char(string="What the options do", compute='_compute_option_help')
    # False once the person can't see the section any more (an app removed,
    # a right taken away): kept, so their choices are back if it returns.
    available = fields.Boolean(default=True, readonly=True)

    @api.depends('days_label', 'team_label', 'has_days', 'has_team')
    def _compute_option_help(self):
        for row in self:
            row.option_help = " · ".join(filter(None, [
                row.has_days and row.days_label, row.has_team and row.team_label])) or ''

    _user_key_unique = models.Constraint(
        'UNIQUE(user_id, key)', 'Each My Day section appears once per person.')

    @api.constrains('limit', 'days')
    def _check_numbers(self):
        for row in self:
            if not 1 <= row.limit <= 30:
                raise ValidationError(_("Items must be between 1 and 30."))
            if row.has_days and not 0 <= row.days <= 90:
                raise ValidationError(_("Days ahead must be between 0 and 90."))

    # Preferences are saved with elevated rights (res.users' own fields, see
    # SELF_WRITEABLE_FIELDS), so these checks, not record rules, keep a person
    # to their own rows and to the fields that are theirs to change.

    def _check_own(self, vals=None):
        if self.env.user._is_admin():
            return
        if any(row.user_id != self.env.user for row in self):
            raise AccessError(_("You can only change your own My Day."))
        if vals and set(vals) - USER_FIELDS:
            raise AccessError(_("Only the section's own options can be changed."))

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user._is_admin():
            raise AccessError(_("My Day creates its sections itself."))
        return super().create(vals_list)

    def write(self, vals):
        self._check_own(vals)
        return super().write(vals)

    def unlink(self):
        if not self.env.user._is_admin():
            raise AccessError(_("Hide a section instead: untick Show."))
        return super().unlink()

    # My Day's own bookkeeping (new sections, titles, availability): private
    # methods, so never callable from outside, past the checks above.

    @api.model
    def _my_day_create(self, vals_list):
        return models.Model.create(self.sudo(), vals_list)

    def _my_day_write(self, vals):
        return models.Model.write(self.sudo(), vals)
