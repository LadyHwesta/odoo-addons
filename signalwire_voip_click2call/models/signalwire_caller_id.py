# -*- coding: utf-8 -*-
"""Which number an outside call goes out as, by company.

A softphone or desk phone on a phone account with "Choose Caller ID by
Company" asks Odoo for every outside call (controllers/outbound.py). The
call goes out as the main number of the first company that applies:

1. the record the call was started from (clicked in Odoo),
2. the contact being called: their company, else the company of their
   latest quote, invoice, lead or ticket,
3. the company the person was working in (Odoo's current company),
4. their own company,
falling back to their Calls Out As number. A branch without a main number
uses its parent's. 911 always goes out as the Calls Out As number (its
E911 address is the one registered).

Clicking call in Odoo leaves a short-lived note (signalwire.outbound.intent)
so the provider's request a moment later knows the record and company.
"""
from datetime import timedelta

from odoo import _, api, fields, models

from ..controllers.outbound import dialed_number

INTENT_SECONDS = 120
EMERGENCY = ('911', '933')
DOCUMENT_MODELS = ['sale.order', 'account.move', 'crm.lead', 'helpdesk.ticket']


class ResCompany(models.Model):
    _inherit = 'res.company'

    signalwire_main_number_id = fields.Many2one(
        'signalwire.phone_number', string="Main Phone Number",
        domain="[('company_id', 'in', [id, False])]",
        help="Outside calls made for this company go out as this number. "
             "A branch without one uses its parent company's.")

    def _signalwire_main_number(self):
        company = self
        while company:
            if company.signalwire_main_number_id:
                return company.signalwire_main_number_id
            company = company.parent_id
        return self.env['signalwire.phone_number']


class SignalWireOutboundIntent(models.Model):
    """'This person is about to call this number, for this company':
    left by the browser just before dialing, read by the provider's
    request a moment later. Kept for INTENT_SECONDS."""
    _name = 'signalwire.outbound.intent'
    _description = 'Outside Call About to Start'
    _order = 'id desc'

    user_id = fields.Many2one('res.users', required=True, ondelete='cascade', index=True)
    number = fields.Char(required=True, index=True)
    company_id = fields.Many2one('res.company', ondelete='cascade')
    caller_number_id = fields.Many2one('signalwire.phone_number', ondelete='cascade')

    @api.model
    def _find(self, user, number):
        since = fields.Datetime.now() - timedelta(seconds=INTENT_SECONDS)
        return self.search([('user_id', '=', user.id), ('number', '=', number),
                            ('create_date', '>=', since)], limit=1)

    @api.autovacuum
    def _gc_old_intents(self):
        self.search([('create_date', '<', fields.Datetime.now() - timedelta(hours=1))]).unlink()


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _signalwire_contact_company(self, number):
        """The company of who's being called: theirs, else their latest
        document's, within this person's companies."""
        self.ensure_one()
        partner = self._signalwire_match_partner(number)
        if not partner:
            return self.env['res.company']
        mine = self.company_ids
        if partner.company_id in mine:
            return partner.company_id
        commercial = partner.commercial_partner_id
        latest = None
        for model in DOCUMENT_MODELS:
            if model not in self.env:
                continue
            Model = self.env[model].sudo()
            if 'partner_id' not in Model._fields or 'company_id' not in Model._fields:
                continue
            record = Model.search([('partner_id', 'child_of', commercial.id), ('company_id', 'in', mine.ids)],
                                  order='write_date desc', limit=1)
            if record and (latest is None or record.write_date > latest.write_date):
                latest = record
        return latest.company_id if latest else self.env['res.company']

    def _signalwire_record_company(self, res_model, res_id):
        if not (res_model and res_id) or res_model not in self.env:
            return self.env['res.company']
        record = self.env[res_model].browse(int(res_id)).exists()
        if not record or 'company_id' not in record._fields or not record.has_access('read'):
            return self.env['res.company']
        return record.company_id

    def _signalwire_choose_caller(self, number, record_company=None, current_company=None):
        """(company, phone number record) for an outside call to `number`."""
        self.ensure_one()
        if number in EMERGENCY:
            return self.company_id, self.signalwire_outbound_number_id
        candidates = [record_company, self._signalwire_contact_company(number), current_company, self.company_id]
        for company in candidates:
            if company and company in self.company_ids:
                caller = company._signalwire_main_number()
                if caller:
                    return company, caller
        return self.company_id, self.signalwire_outbound_number_id

    @api.model
    def signalwire_note_outbound_call(self, number, res_model=False, res_id=False):
        """Called by the softphone just before it dials. Returns what the
        call will show, for a 'Calling as ...' note."""
        user = self.env.user
        dialed = dialed_number(number or '')
        if not dialed or not user._signalwire_caller_by_company():
            return {}
        company, caller = user._signalwire_choose_caller(
            dialed, user._signalwire_record_company(res_model, res_id), self.env.company)
        self.env['signalwire.outbound.intent'].sudo().create({
            'user_id': user.id, 'number': dialed, 'company_id': company.id or False,
            'caller_number_id': caller.id or False})
        if not caller:
            return {}
        return {'label': _("Calling as %(company)s (%(number)s)", company=company.name, number=caller.name)}

    def _signalwire_caller_by_company(self):
        self.ensure_one()
        return bool(self.signalwire_server_id.sudo().caller_id_by_company)

    def _signalwire_outbound_caller(self, number):
        """For the provider's request: the number this call goes out as."""
        self.ensure_one()
        if number in EMERGENCY:
            return self.signalwire_outbound_number_id
        intent = self.env['signalwire.outbound.intent'].sudo()._find(self, number)
        if intent and intent.caller_number_id:
            return intent.caller_number_id
        return self._signalwire_choose_caller(number)[1]
