# -*- coding: utf-8 -*-
import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SignalWirePhoneNumber(models.Model):
    """Extends signalwire.phone_number (already extended once, in
    reseller_subscriptions, for contract_id/payment_token_id) with the
    actual 10DLC opt-in: a number with no campaign_id simply can't
    send SMS yet - action_request_sms_enablement() is the deliberate,
    per-number trigger a customer (or staff) has to take, matching the
    "opt-in only, not automatic at checkout" decision.
    """
    _name = 'signalwire.phone_number'
    _inherit = 'signalwire.phone_number'

    campaign_id = fields.Many2one('signalwire.campaign', copy=False)
    campaign_assignment_state = fields.Selection(
        [('none', 'Not Requested'), ('pending', 'Pending'), ('approved', 'Approved'),
         ('rejected', 'Rejected')],
        default='none', required=True, copy=False,
        help="Mirrors the real order/number-assignment state from "
             "SignalWire's own API, same \"reflect, don't guess\" "
             "approach as signalwire.brand/signalwire.campaign.")

    def action_request_sms_enablement(self):
        """The actual opt-in trigger. Requires the owning partner to
        already have an approved (or at least submitted) campaign -
        this method doesn't create one itself; the portal routes a
        customer with no campaign yet to the brand/campaign form
        first (see controllers/portal.py).
        """
        self.ensure_one()
        if self.campaign_id:
            raise UserError(_(
                "%(number)s already has a campaign assigned.", number=self.name))
        partner = self.partner_id
        campaign = self.env['signalwire.campaign'].search([
            ('partner_id', '=', partner.id),
            ('state', 'in', ('submitted', 'pending', 'approved')),
        ], limit=1, order='create_date desc')
        if not campaign:
            raise UserError(_(
                "%(partner)s has no submitted 10DLC campaign yet - "
                "register one first.", partner=partner.name))

        client = self.subproject_id.server_id._get_client()
        client.registry_post(
            f'campaigns/{campaign.signalwire_campaign_id}/orders',
            phone_numbers=[{'sid': self.sid}])
        self.write({'campaign_id': campaign.id, 'campaign_assignment_state': 'pending'})

    def _cron_check_campaign_assignment_status(self):
        for number in self.search([
                ('campaign_assignment_state', '=', 'pending'), ('campaign_id', '!=', False)]):
            try:
                # Savepoint per record - same reasoning as
                # signalwire.brand's own _cron_check_brand_status.
                with self.env.cr.savepoint():
                    result = number.subproject_id.server_id._get_client().registry_get(
                        f'campaigns/{number.campaign_id.signalwire_campaign_id}/numbers')
                    for entry in result.get('data', []):
                        if entry.get('phone_number', {}).get('id') == number.sid:
                            new_state = entry.get('state')
                            if new_state and new_state != number.campaign_assignment_state:
                                number.campaign_assignment_state = new_state
                            break
            except Exception:
                _logger.exception(
                    "signalwire_10dlc: assignment status check failed for number %s", number.id)
