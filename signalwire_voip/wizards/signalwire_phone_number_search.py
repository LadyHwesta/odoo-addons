# -*- coding: utf-8 -*-
from odoo import _, api, models, fields
from odoo.exceptions import UserError


class SignalWirePhoneNumberSearch(models.TransientModel):
    """Staff-driven number search + purchase, opened from a
    subproject's own form. Search is free and re-runnable; purchase is
    real money - each result row gets its own explicit Purchase
    button rather than a bulk action, so nothing gets bought by
    accident.
    """
    _name = 'signalwire.phone_number.search'
    _description = 'Search SignalWire Phone Numbers'

    subproject_id = fields.Many2one('signalwire.subproject', required=True)
    country = fields.Selection(
        [('US', 'United States'), ('CA', 'Canada')], default='US', required=True)
    area_code = fields.Char(
        help="Optional - narrows results to this area code (US/CA only).")
    result_ids = fields.One2many(
        'signalwire.phone_number.search.result', 'wizard_id', readonly=True)

    def action_search(self):
        self.ensure_one()
        self.result_ids.unlink()
        numbers = self.subproject_id.server_id.search_available_numbers(
            self.subproject_id.account_sid, self.country, area_code=self.area_code)
        self.result_ids = [(0, 0, {'phone_number': n}) for n in numbers]
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class SignalWirePhoneNumberSearchResult(models.TransientModel):
    _name = 'signalwire.phone_number.search.result'
    _description = 'SignalWire Phone Number Search Result'

    wizard_id = fields.Many2one(
        'signalwire.phone_number.search', required=True, ondelete='cascade')
    phone_number = fields.Char(readonly=True)

    def action_purchase(self):
        self.ensure_one()
        self.wizard_id.subproject_id.purchase_number(self.phone_number)
        return {'type': 'ir.actions.act_window_close'}
