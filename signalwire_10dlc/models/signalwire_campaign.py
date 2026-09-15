# -*- coding: utf-8 -*-
"""One messaging use case under a signalwire.brand - confirmed live
2026-09-15 as a real, working resource nested under a brand
(POST/GET /api/relay/rest/registry/beta/brands/{brand_id}/campaigns),
while its own numbers/orders sub-resources are addressed directly by
campaign_id alone, no brand prefix (see signalwire_phone_number.py).

sms_use_case's allowed values are sourced from SignalWire's own docs,
not independently confirmed for every value - only 'CUSTOMER_CARE' has
been seen in real live data (the user's own campaign).
"""
import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

MINIMUM_COMMITMENT_MONTHS = 3

SMS_USE_CASES = [
    ('2FA', 'Two-Factor Authentication'), ('ACCOUNT_NOTIFICATION', 'Account Notification'),
    ('AGENTS_FRANCHISES', 'Agents/Franchises'), ('CARRIER_EXEMPT', 'Carrier Exempt'),
    ('CHARITY', 'Charity'), ('CUSTOMER_CARE', 'Customer Care'),
    ('DELIVERY_NOTIFICATION', 'Delivery Notification'), ('EMERGENCY', 'Emergency'),
    ('FRAUD_ALERT', 'Fraud Alert'), ('HIGHER_EDUCATION', 'Higher Education'),
    ('K12_EDUCATION', 'K-12 Education'), ('LOW_VOLUME_MIXED', 'Low Volume Mixed'),
    ('MARKETING', 'Marketing'), ('MIXED', 'Mixed'), ('POLITICAL', 'Political'),
    ('POLITICAL_SECTION_527', 'Political (Section 527)'), ('POLLING_VOTING', 'Polling/Voting'),
    ('PROXY', 'Proxy'), ('PUBLIC_SERVICE_ANNOUNCEMENT', 'Public Service Announcement'),
    ('SECURITY_ALERT', 'Security Alert'), ('SOCIAL', 'Social'), ('SWEEPSTAKE', 'Sweepstake'),
    ('TRIAL', 'Trial'), ('UCAAS_HIGH_VOLUME', 'UCaaS High Volume'),
    ('UCAAS_LOW_VOLUME', 'UCaaS Low Volume'),
]


class SignalWireCampaign(models.Model):
    _name = 'signalwire.campaign'
    _description = 'A SignalWire 10DLC Campaign'
    _inherit = ['mail.thread', 'contract.billing.mixin']

    brand_id = fields.Many2one('signalwire.brand', required=True, tracking=True)
    partner_id = fields.Many2one(
        'res.partner', related='brand_id.partner_id', store=True, readonly=True)
    name = fields.Char(required=True)
    sms_use_case = fields.Selection(SMS_USE_CASES, required=True)
    description = fields.Text(required=True)
    sample1 = fields.Char(string="Sample Message 1", required=True)
    sample2 = fields.Char(string="Sample Message 2")
    sample3 = fields.Char(string="Sample Message 3")
    sample4 = fields.Char(string="Sample Message 4")
    sample5 = fields.Char(string="Sample Message 5")
    message_flow = fields.Text(
        required=True, help="How a customer ends up receiving these messages.")
    opt_in_message = fields.Char(required=True)
    opt_out_message = fields.Char(required=True)
    help_message = fields.Char(required=True)
    opt_in_keywords = fields.Char(default='SUBSCRIBE', required=True)
    opt_out_keywords = fields.Char(default='STOP', required=True)
    help_keywords = fields.Char(default='HELP', required=True)
    signalwire_campaign_id = fields.Char(readonly=True, copy=False)
    state = fields.Selection(
        [('draft', 'Draft'), ('submitted', 'Submitted'), ('pending', 'Pending'),
         ('approved', 'Approved'), ('rejected', 'Rejected'), ('failed', 'Failed'),
         ('cancelled', 'Cancelled')],
        default='draft', required=True, tracking=True,
        help="'draft' through 'failed' mirror whatever state string "
             "SignalWire's own API reports, same approach as "
             "signalwire.brand's own state field - 'cancelled' is the "
             "one value this model sets itself, via action_cancel().")
    contract_id = fields.Many2one('contract.contract', string="Billing Contract", copy=False)
    payment_token_id = fields.Many2one(
        'payment.token', string="Saved Payment Method", copy=False)
    min_commitment_end_date = fields.Date(
        readonly=True, copy=False,
        help="Submission date + 3 months - the real minimum "
             "commitment SignalWire/the carrier charges upfront for. "
             "action_cancel() refuses before this date.")

    def action_submit(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_("%(campaign)s has already been submitted.", campaign=self.name))
        if self.brand_id.state not in ('submitted', 'pending', 'approved'):
            raise UserError(_(
                "%(brand)s hasn't been submitted yet - submit the brand first.",
                brand=self.brand_id.company_name))

        client = self.brand_id.server_id._get_client()
        result = client.registry_post(
            f'brands/{self.brand_id.signalwire_brand_id}/campaigns',
            name=self.name, sms_use_case=self.sms_use_case, description=self.description,
            sample1=self.sample1, sample2=self.sample2 or '', sample3=self.sample3 or '',
            sample4=self.sample4 or '', sample5=self.sample5 or '',
            message_flow=self.message_flow, opt_in_message=self.opt_in_message,
            opt_out_message=self.opt_out_message, help_message=self.help_message,
            opt_in_keywords=self.opt_in_keywords, opt_out_keywords=self.opt_out_keywords,
            help_keywords=self.help_keywords,
        )
        today = fields.Date.context_today(self)
        self.write({
            'signalwire_campaign_id': result.get('id'),
            'state': result.get('state', 'submitted'),
            'min_commitment_end_date': today + relativedelta(months=MINIMUM_COMMITMENT_MONTHS),
        })
        self._start_billing()

    def _start_billing(self):
        """Creates the contract + its recurring line - silently does
        nothing if no signalwire_10dlc.product_campaign_fee product
        exists or its price is 0, same reasoning as
        signalwire.brand._charge_brand_fee.
        """
        self.ensure_one()
        product = self.env.ref(
            'signalwire_10dlc.product_signalwire_campaign_fee', raise_if_not_found=False)
        if not product or not product.list_price or self.contract_id:
            return
        contract = self.env['contract.contract'].create({
            'name': _("%(campaign)s - 10DLC Campaign", campaign=self.name),
            'partner_id': self.partner_id.id,
            'contract_type': 'sale',
            'line_recurrence': True,
            'contract_line_ids': [(0, 0, {
                'product_id': product.product_variant_id.id,
                'name': _("10DLC campaign fee - %(campaign)s", campaign=self.name),
                'quantity': 1,
                'price_unit': product.list_price,
                'date_start': fields.Date.context_today(self),
                'recurring_interval': 1,
                'recurring_rule_type': 'monthly',
                'recurring_invoicing_type': 'pre-paid',
            })],
        })
        self.contract_id = contract.id

    def action_cancel(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        if self.min_commitment_end_date and today < self.min_commitment_end_date:
            raise UserError(_(
                "%(campaign)s can't be cancelled before %(date)s - the "
                "3-month minimum commitment is charged upfront and isn't "
                "refundable.", campaign=self.name, date=self.min_commitment_end_date))
        if self.contract_id:
            self.contract_id.contract_line_ids.filtered(
                lambda line: not line.date_end or line.date_end >= today
            ).write({'date_end': today})
        self.state = 'cancelled'

    @api.model
    def _cron_check_campaign_status(self):
        for campaign in self.search([
                ('state', 'in', ['submitted', 'pending']),
                ('signalwire_campaign_id', '!=', False)]):
            try:
                # Savepoint per record - see signalwire.brand's own
                # _cron_check_brand_status for why a bare try/except
                # around just the API call isn't enough.
                with self.env.cr.savepoint():
                    result = campaign.brand_id.server_id._get_client().registry_get(
                        f'brands/{campaign.brand_id.signalwire_brand_id}/campaigns/'
                        f'{campaign.signalwire_campaign_id}')
                    new_state = result.get('state')
                    if new_state and new_state != campaign.state:
                        campaign.state = new_state
            except Exception:
                _logger.exception(
                    "signalwire_10dlc: status check failed for campaign %s", campaign.id)
