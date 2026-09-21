# -*- coding: utf-8 -*-
from odoo import api, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model_create_multi
    def create(self, vals_list):
        """A portal login is very often created *after* an admin has
        already set the partner's own signalwire_portal_support_tier
        (the partner usually exists first, then gets invited to the
        portal) - res.partner's own create()/write() sync only ever
        looks at *existing* portal users at the time the tier is
        touched, so without this, a tier set before the invite would
        silently never take effect. Re-running the same sync here,
        from the user side, closes that gap regardless of which order
        the two records were created in.
        """
        users = super().create(vals_list)
        users.mapped('partner_id')._sync_signalwire_portal_group()
        return users
