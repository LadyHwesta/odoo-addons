# -*- coding: utf-8 -*-
from odoo import models, fields


class SignalWirePhoneNumberSearch(models.TransientModel):
    """Staff-driven number search + purchase, opened from a
    subproject's own form. Search is free and re-runnable; purchase is
    real money - each result row gets its own explicit Purchase
    button rather than a bulk action, so nothing gets bought by
    accident. Same filters as SignalWire's own dashboard search (see
    signalwire.server.search_numbers).
    """
    _name = 'signalwire.phone_number.search'
    _description = 'Search SignalWire Phone Numbers'

    subproject_id = fields.Many2one('signalwire.subproject', required=True)
    number_type = fields.Selection(
        [('local', 'Local'), ('toll_free', 'Toll-free')], default='local', required=True)
    match = fields.Selection(
        [('starts_with', 'Starts with'), ('contains', 'Contains'), ('ends_with', 'Ends with')],
        default='contains', required=True)
    pattern = fields.Char(
        string="Digits or Letters",
        help="Optional. 3 to 7 digits; letters count as their keypad digits (BEAR = 2327).")
    area_code = fields.Char(help="Optional. Local numbers only.")
    region_id = fields.Many2one(
        'res.country.state', string="State",
        domain="[('country_id.code', 'in', ('US', 'CA'))]",
        help="Optional. Local numbers only.")
    city = fields.Char(help="Optional, and only with a state.")
    result_ids = fields.One2many(
        'signalwire.phone_number.search.result', 'wizard_id', readonly=True)

    def action_search(self):
        self.ensure_one()
        self.result_ids.unlink()
        local = self.number_type == 'local'
        numbers = self.subproject_id.server_id.search_numbers(
            number_type=self.number_type, match=self.match, pattern=self.pattern,
            area_code=self.area_code if local else None,
            region=self.region_id.code if local else None,
            city=self.city if local else None)
        self.result_ids = [(0, 0, {
            'phone_number': n['e164'],
            'location': ', '.join(p for p in (n['rate_center'].title(), n['region']) if p),
            'capabilities': ', '.join(n['capabilities']),
        }) for n in numbers]
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _purchase_number(self, phone_number):
        """Buy one number into the subproject and return the new
        signalwire.phone_number. A hook, so a billing module can check
        things before the purchase and bill the number after it."""
        self.ensure_one()
        return self.subproject_id.purchase_number(phone_number)


class SignalWirePhoneNumberSearchResult(models.TransientModel):
    _name = 'signalwire.phone_number.search.result'
    _description = 'SignalWire Phone Number Search Result'

    wizard_id = fields.Many2one(
        'signalwire.phone_number.search', required=True, ondelete='cascade')
    phone_number = fields.Char(readonly=True)
    location = fields.Char(readonly=True)
    capabilities = fields.Char(readonly=True)

    def action_purchase(self):
        self.ensure_one()
        self.wizard_id._purchase_number(self.phone_number)
        return {'type': 'ir.actions.act_window_close'}
