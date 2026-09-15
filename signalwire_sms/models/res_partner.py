# -*- coding: utf-8 -*-
from odoo import _, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def action_open_signalwire_sms_compose(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Send SMS"),
            'res_model': 'signalwire.sms.compose',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_id': self.id,
                'default_to': self.phone,
            },
        }
