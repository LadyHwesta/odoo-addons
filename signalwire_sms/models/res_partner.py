# -*- coding: utf-8 -*-
from odoo import _, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    sms_blocked = fields.Boolean(
        tracking=True,
        help="This contact replied STOP to one of our texts, so no "
             "texts will be sent to them until they reply START or "
             "UNSTOP, which clears this automatically. Required by "
             "the phone carriers.")

    def _sms_handle_custom_keyword(self, body):
        """Extension point for an inbound SMS body that didn't match
        any of the standard STOP/START/HELP keyword families (see
        signalwire.sms._handle_inbound_keywords) - a no-op here, since
        this module has no notion of its own beyond the carrier-
        mandated keywords. A module layering its own consent workflow
        on top (e.g. a double opt-in's own "Y"/"N" confirmation reply)
        overrides this to react to its own custom replies.
        """
        return False

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
