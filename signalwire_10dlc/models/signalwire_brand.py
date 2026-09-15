# -*- coding: utf-8 -*-
"""One resold customer's real business identity, registered with The
Campaign Registry via SignalWire's Registry API
(SignalWireClient.registry_get/registry_post, added in signalwire_voip)
- confirmed live 2026-09-15 against the user's own account
(POST/GET /api/relay/rest/registry/beta/brands, no subaccount scoping
found anywhere - brands live flat at the top-level account regardless
of which resold customer they're actually for).

legal_entity_type and company_vertical's exact allowed values are
sourced from SignalWire's own docs, not independently confirmed for
every value - only 'PRIVATE_PROFIT' and 'TECHNOLOGY' respectively have
been seen in real live data (the user's own brand). If SignalWire ever
rejects a value here, that's the real API disagreeing with its own
documented enum, not a guess on this module's part.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

LEGAL_ENTITY_TYPES = [
    ('PRIVATE_PROFIT', 'Private, For-Profit'),
    ('PUBLIC_PROFIT', 'Public, For-Profit'),
    ('NON_PROFIT', 'Non-Profit'),
    ('GOVERNMENT', 'Government'),
]

COMPANY_VERTICALS = [
    ('AGRICULTURE', 'Agriculture'), ('COMMUNICATION', 'Communication'),
    ('CONSTRUCTION', 'Construction'), ('EDUCATION', 'Education'),
    ('ENERGY', 'Energy'), ('ENTERTAINMENT', 'Entertainment'),
    ('FINANCIAL', 'Financial'), ('GAMBLING', 'Gambling'),
    ('GOVERNMENT', 'Government'), ('HEALTHCARE', 'Healthcare'),
    ('HOSPITALITY', 'Hospitality'), ('HUMAN_RESOURCES', 'Human Resources'),
    ('INSURANCE', 'Insurance'), ('LEGAL', 'Legal'),
    ('MANUFACTURING', 'Manufacturing'), ('NGO', 'NGO'),
    ('POLITICAL', 'Political'), ('POSTAL', 'Postal'),
    ('PROFESSIONAL', 'Professional'), ('REAL_ESTATE', 'Real Estate'),
    ('RETAIL', 'Retail'), ('TECHNOLOGY', 'Technology'),
    ('TRANSPORTATION', 'Transportation'),
]

# There is no single SignalWire config record the way hestiacp.server/
# namecheap.server/signalwire.server hold credentials - registry calls
# reuse whichever signalwire.server already exists (there's normally
# just one), matching how signalwire_sms's own portal already assumes
# a single reseller account.


class SignalWireBrand(models.Model):
    _name = 'signalwire.brand'
    _description = "A Resold Customer's SignalWire 10DLC Brand"
    _inherit = ['mail.thread']
    _rec_name = 'company_name'

    partner_id = fields.Many2one(
        'res.partner', required=True, tracking=True,
        help="The actual business this brand identifies - never the "
             "reseller's own. One partner should only need one brand.")
    server_id = fields.Many2one(
        'signalwire.server', required=True, default=lambda self: self.env[
            'signalwire.server'].search([], limit=1),
        help="Whichever SignalWire project's Registry API this "
             "submits through - brands/campaigns live at the "
             "top-level project, not per-subproject.")
    name = fields.Char(required=True, help="Marketing/brand name.")
    company_name = fields.Char(required=True, help="Legal business name.")
    contact_email = fields.Char(required=True)
    contact_phone = fields.Char(required=True)
    ein_issuing_country = fields.Char(default='US', required=True)
    legal_entity_type = fields.Selection(LEGAL_ENTITY_TYPES, required=True)
    ein = fields.Char(
        string="EIN", required=True,
        help="Tax ID/EIN - the customer submits this themselves via "
             "the portal, so it can't be field-level restricted to "
             "System group the way upcloud.account's own API token "
             "is (that would block the very submission this exists "
             "for). Restricted at the record level instead: an "
             "ir.rule scopes a portal user to their own brand only, "
             "and no plain internal user (base.group_user) gets any "
             "access to this model at all - System group only,"
             " see security/signalwire_10dlc_security.xml.")
    company_address = fields.Text(required=True)
    company_website = fields.Char(required=True)
    company_vertical = fields.Selection(COMPANY_VERTICALS, required=True)
    csp_self_registered = fields.Boolean(
        string="Already Has a TCR Brand",
        help="Check this if the customer already registered a brand "
             "directly with The Campaign Registry (e.g. through "
             "another SMS vendor) - lets them reference that existing "
             "brand instead of submitting all their business details "
             "again.")
    csp_brand_reference = fields.Char(
        string="Existing TCR Brand ID",
        help="Required if 'Already Has a TCR Brand' is checked.")
    signalwire_brand_id = fields.Char(readonly=True, copy=False)
    state = fields.Selection(
        [('draft', 'Draft'), ('submitted', 'Submitted'), ('pending', 'Pending'),
         ('approved', 'Approved'), ('rejected', 'Rejected'), ('failed', 'Failed')],
        default='draft', required=True, tracking=True,
        help="Mirrored directly from whatever state string "
             "SignalWire's own API reports - not a hardcoded "
             "transition graph, since the real state machine beyond "
             "\"pending\" hasn't been independently confirmed.")

    def action_submit(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_("%(brand)s has already been submitted.", brand=self.company_name))
        if self.csp_self_registered and not self.csp_brand_reference:
            raise UserError(_(
                "Enter the existing TCR Brand ID, or uncheck "
                "'Already Has a TCR Brand'."))

        client = self.server_id._get_client()
        if self.csp_self_registered:
            payload = {
                'csp_self_registered': True,
                'name': self.name,
                'csp_brand_reference': self.csp_brand_reference,
            }
        else:
            payload = {
                'name': self.name,
                'company_name': self.company_name,
                'contact_email': self.contact_email,
                'contact_phone': self.contact_phone,
                'ein_issuing_country': self.ein_issuing_country,
                'legal_entity_type': self.legal_entity_type,
                'ein': self.ein,
                'company_address': self.company_address,
                'company_website': self.company_website,
                'company_vertical': self.company_vertical,
            }
        result = client.registry_post('brands', **payload)
        self.write({
            'signalwire_brand_id': result.get('id'),
            'state': result.get('state', 'submitted'),
        })
        self._charge_brand_fee()

    def _charge_brand_fee(self):
        """A one-time invoice, not a recurring contract line - the
        brand registration fee is charged once, at submission.
        Silently does nothing if no signalwire_10dlc.product_brand_fee
        product exists or its price is 0 - a reseller who wants to eat
        this cost themselves shouldn't be forced into an invoice.
        """
        self.ensure_one()
        product = self.env.ref(
            'signalwire_10dlc.product_signalwire_brand_fee', raise_if_not_found=False)
        if not product or not product.list_price:
            return
        self.env['account.move'].sudo().create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'invoice_origin': self.company_name,
            'invoice_line_ids': [(0, 0, {
                'product_id': product.product_variant_id.id,
                'name': _("10DLC brand registration - %(brand)s", brand=self.company_name),
                'quantity': 1,
                'price_unit': product.list_price,
            })],
        })

    @api.model
    def _cron_check_brand_status(self):
        for brand in self.search([
                ('state', 'in', ['submitted', 'pending']),
                ('signalwire_brand_id', '!=', False)]):
            try:
                # A savepoint, not a bare try/except: a failed write
                # (e.g. SignalWire reporting a state string this
                # Selection field hasn't enumerated) poisons the whole
                # surrounding Postgres transaction, not just this
                # iteration - every later brand's write in the same
                # cron run would then fail too. The savepoint rolls
                # back only this one record's attempt.
                with self.env.cr.savepoint():
                    result = brand.server_id._get_client().registry_get(
                        f'brands/{brand.signalwire_brand_id}')
                    new_state = result.get('state')
                    if new_state and new_state != brand.state:
                        brand.state = new_state
            except Exception:
                _logger.exception(
                    "signalwire_10dlc: status check failed for brand %s", brand.id)
