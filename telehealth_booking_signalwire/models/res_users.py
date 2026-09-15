# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError

USAGE_PRODUCT_XML_ID = 'telehealth_booking_signalwire.product_telehealth_premium_usage'


class ResUsers(models.Model):
    _inherit = 'res.users'

    signalwire_video_subproject_id = fields.Many2one(
        'signalwire.subproject', readonly=True, copy=False,
        help="This provider's own SignalWire subproject for premium "
             "telehealth video - created lazily on first use, not at "
             "upgrade time.")
    signalwire_video_contract_id = fields.Many2one(
        'contract.contract', readonly=True, copy=False,
        help="The recurring, metered-usage contract billing this "
             "provider's premium video minutes - same lazy creation "
             "as the subproject above.")

    def action_upgrade_telehealth_video(self):
        """Self-service upgrade - just flips the tier. Actual billing
        infrastructure (subproject, contract) is provisioned lazily,
        on the first booking that actually requests a premium video
        link (see calendar.event._provision_signalwire_room), not
        eagerly here - upgrading shouldn't create real SignalWire
        resources or a contract nobody's used yet.
        """
        self.ensure_one()
        if self.telehealth_video_tier == 'premium':
            raise UserError(_("%(user)s is already on Premium.", user=self.name))
        self.telehealth_video_tier = 'premium'

    def action_downgrade_telehealth_video(self):
        """Back to Basic. Doesn't release the SignalWire subproject or
        close the contract - a provider who upgrades again later
        should get the same one back rather than accumulating a new
        one per switch. Any existing contract just stops getting new
        usage to bill once no more premium bookings happen.
        """
        self.ensure_one()
        if self.telehealth_video_tier == 'basic':
            raise UserError(_("%(user)s is already on Basic.", user=self.name))
        self.telehealth_video_tier = 'basic'

    def _ensure_telehealth_video_billing(self):
        """Make sure this provider has an active subproject + metered
        video contract line - called the first time a premium video
        room is actually provisioned for one of their bookings.
        """
        self.ensure_one()
        if not self.signalwire_video_subproject_id:
            server = self.env['signalwire.server'].search([], limit=1)
            subproject = self.env['signalwire.subproject'].create({
                'name': f'{self.name} - Telehealth Video',
                'server_id': server.id,
                'partner_id': self.partner_id.id,
            })
            subproject.action_provision()
            self.signalwire_video_subproject_id = subproject.id

        if not self.signalwire_video_contract_id:
            usage_product = self.env.ref(USAGE_PRODUCT_XML_ID)
            contract = self.env['contract.contract'].create({
                'name': f'{self.name} - Premium Telehealth Video',
                'partner_id': self.partner_id.id,
                'contract_type': 'sale',
                'line_recurrence': True,
                'contract_line_ids': [(0, 0, {
                    'product_id': usage_product.id,
                    'name': 'Premium Telehealth Video - usage',
                    'quantity': 1,
                    'price_unit': 0.0,
                    'date_start': fields.Date.context_today(self),
                    'recurring_interval': 1,
                    'recurring_rule_type': 'monthly',
                    'recurring_invoicing_type': 'post-paid',
                    'is_signalwire_metered': True,
                    'signalwire_usage_type': 'video',
                    'signalwire_subproject_id': self.signalwire_video_subproject_id.id,
                })],
            })
            self.signalwire_video_contract_id = contract.id
