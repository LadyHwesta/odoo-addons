# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    signalwire_portal_support_tier = fields.Selection(
        [('none', "None"), ('callback', "Callback Requests"),
         ('live_call', "Live Call")],
        default='none', required=True, string="Portal Support Calling",
        help="Whether this contact's portal login can request a "
             "support callback, or (a step further) place a real "
             "live call to reach an agent directly - live_call "
             "always includes callback too. Portal calling never "
             "reaches an outside number - only a fixed internal "
             "Portal Support queue, by design, regardless of tier.")

    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)
        partners._sync_signalwire_portal_group()
        return partners

    def write(self, vals):
        result = super().write(vals)
        if 'signalwire_portal_support_tier' in vals:
            self._sync_signalwire_portal_group()
        return result

    def _sync_signalwire_portal_group(self):
        """Keeps this partner's own portal login (if any) in sync
        with the SignalWire Portal Calling group - the tier field
        above is the business-facing flag an admin actually edits;
        the group is what the new models' own ir.model.access/ir.rule
        actually gate on, matching Odoo core's own idiom for gating a
        portal *capability* (confirmed by reading how project's own
        portal access rules work) rather than checking a res.partner
        field directly from an ir.rule domain.
        """
        group = self.env.ref(
            'signalwire_voip_portal.group_signalwire_portal_calling',
            raise_if_not_found=False)
        if not group:
            return
        for partner in self:
            portal_users = self.env['res.users'].sudo().search(
                [('partner_id', '=', partner.id)])
            if not portal_users:
                continue
            if partner.signalwire_portal_support_tier != 'none':
                portal_users.write({'group_ids': [(4, group.id)]})
            else:
                portal_users.write({'group_ids': [(3, group.id)]})
