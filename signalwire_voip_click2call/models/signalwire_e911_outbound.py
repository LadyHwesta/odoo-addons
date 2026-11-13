# -*- coding: utf-8 -*-
"""Outbound calling depends on E911.

Softphones and desk phones dial outside numbers directly at the phone
provider, not through Odoo, so the rule is set on each phone there: its
call handler is ``passthrough`` (outside numbers allowed, calling out as the
user's chosen number) only while that number's E911 is active, and
``block-pstn`` (internal calls only) otherwise. A 911 call from a number
with no registered emergency address costs the account $100, and the
caller can't be located; blocking outside calls avoids both.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.signalwire_voip.models.signalwire_api import SignalWireAPIError

_logger = logging.getLogger(__name__)

OUTSIDE_ALLOWED = 'passthrough'
INTERNAL_ONLY = 'block-pstn'


class ResUsers(models.Model):
    _inherit = 'res.users'

    signalwire_outbound_number_id = fields.Many2one(
        'signalwire.phone_number', string="Calls Out As",
        domain="[('company_id', 'in', company_ids)]",
        help="The number outside calls from this person's softphone and desk phones "
             "come from. They can only call outside numbers, 911 included, while "
             "this number's E911 is active.")
    signalwire_outbound_allowed = fields.Boolean(
        string="Can Call Outside Numbers", compute='_compute_signalwire_outbound_allowed')

    @api.depends('signalwire_outbound_number_id.e911_status')
    def _compute_signalwire_outbound_allowed(self):
        for user in self:
            user.signalwire_outbound_allowed = user.signalwire_outbound_number_id.e911_status == 'active'

    def _signalwire_outbound_settings(self):
        self.ensure_one()
        number = self.signalwire_outbound_number_id
        if number and number.e911_status == 'active':
            return {'call_handler': OUTSIDE_ALLOWED, 'send_as': number.name}
        return {'call_handler': INTERNAL_ONLY}

    def _signalwire_sync_outbound(self):
        """Apply the outbound rule to every phone of these users."""
        for user in self:
            settings = user._signalwire_outbound_settings()
            endpoints = []
            if user.signalwire_sip_endpoint_id:
                endpoints.append((user.signalwire_server_id, user.signalwire_sip_endpoint_id))
            for phone in user.signalwire_desk_phone_ids.filtered('signalwire_sip_endpoint_id'):
                endpoints.append((phone.signalwire_server_id, phone.signalwire_sip_endpoint_id))
            for server, endpoint_id in endpoints:
                try:
                    server._get_client().relay_put(f'endpoints/sip/{endpoint_id}', **settings)
                except SignalWireAPIError as exc:
                    raise UserError(_("Couldn't update %(user)s's phone: %(error)s",
                                      user=user.name, error=str(exc))) from exc

    def write(self, vals):
        result = super().write(vals)
        if 'signalwire_outbound_number_id' in vals:
            self._signalwire_sync_outbound()
        return result

    def action_provision_signalwire_sip(self):
        result = super().action_provision_signalwire_sip()
        self._signalwire_sync_outbound()
        return result


class SignalWireDeskPhone(models.Model):
    _inherit = 'signalwire.desk_phone'

    def action_provision(self):
        result = super().action_provision()
        self.user_id._signalwire_sync_outbound()
        return result


class SignalWirePhoneNumber(models.Model):
    _inherit = 'signalwire.phone_number'

    def _on_e911_status_changed(self):
        result = super()._on_e911_status_changed()
        users = self.env['res.users'].sudo().search([('signalwire_outbound_number_id', 'in', self.ids)])
        users._signalwire_sync_outbound()
        return result


class SignalWireServer(models.Model):
    _inherit = 'signalwire.server'

    def action_apply_e911_to_phones(self):
        """Apply the outbound rule to every provisioned phone at once, e.g.
        after first setting people's Calls Out As numbers."""
        users = self.env['res.users'].sudo().search([
            '|', ('signalwire_sip_endpoint_id', '!=', False),
            ('signalwire_desk_phone_ids.signalwire_sip_endpoint_id', '!=', False)])
        users._signalwire_sync_outbound()
        allowed = users.filtered('signalwire_outbound_allowed')
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {
                'title': _("E911 rule applied"),
                'message': _("%(ok)s people can call outside numbers; %(blocked)s are internal-only "
                             "until their Calls Out As number has active E911.",
                             ok=len(allowed), blocked=len(users - allowed)),
                'type': 'success', 'sticky': False,
            },
        }
