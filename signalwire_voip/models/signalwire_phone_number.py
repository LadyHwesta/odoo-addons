# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .signalwire_api import SignalWireAPIError
from .signalwire_e911 import E911_STATES


class SignalWirePhoneNumber(models.Model):
    """A phone number actually purchased into a subproject. Release is
    a real, billable-going-forward change (frees the number back to
    SignalWire, stops its monthly charge) - not undoable from Odoo's
    side once done, same class of one-way action as HestiaCP account
    termination.
    """
    _name = 'signalwire.phone_number'
    _description = 'Phone Number'
    _rec_name = 'name'

    name = fields.Char(string="Phone Number", required=True, help="E.164 format.")
    sid = fields.Char(
        string="SID", required=True,
        help="The phone provider's ID for this number, needed to release it.")
    subproject_id = fields.Many2one(
        'signalwire.subproject', string="Sub-account", required=True, ondelete='cascade')
    partner_id = fields.Many2one(
        related='subproject_id.partner_id', store=True, string="Customer")
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company,
        help="Which company this number belongs to. One phone account "
             "can serve every company in the database, but a number only "
             "ever rings its own company's people, groups and menus.")
    active = fields.Boolean(default=True)
    number_use = fields.Selection(
        [('own', "Our Numbers"), ('customer', "Customer Numbers")],
        string="Used By", compute='_compute_number_use', store=True,
        help="Our Numbers: no customer, or the customer is one of our own "
             "companies. Customer Numbers: resold to a customer.")

    @api.depends('subproject_id.partner_id')
    def _compute_number_use(self):
        ours = self.env['res.company'].sudo().search([]).partner_id
        for number in self:
            partner = number.subproject_id.partner_id
            number.number_use = 'customer' if partner and partner not in ours else 'own'

    def action_release(self):
        self.ensure_one()
        client = self.subproject_id.server_id._get_client()
        client.compat_delete(
            f'Accounts/{self.subproject_id.account_sid}/'
            f'IncomingPhoneNumbers/{self.sid}.json')
        self.active = False


class SignalWirePhoneNumberE911(models.Model):
    """Enhanced 911 on a number: which registered address it uses, and the
    carrier's status for it (see signalwire_e911.py)."""
    _inherit = 'signalwire.phone_number'

    e911_address_id = fields.Many2one(
        'signalwire.e911.address', string="Emergency Address", copy=False,
        domain="[('state', '=', 'registered')]",
        help="Where 911 calls from this number are sent. The number can't call "
             "outside numbers until this is active.")
    e911_status = fields.Selection(
        E911_STATES, string="E911", default='none', required=True, readonly=True, copy=False)
    e911_checked_at = fields.Datetime(string="E911 Checked", readonly=True, copy=False)
    e911_active = fields.Boolean(compute='_compute_e911_active', store=True)

    @api.depends('e911_status')
    def _compute_e911_active(self):
        for number in self:
            number.e911_active = number.e911_status == 'active'

    def _e911_path(self):
        self.ensure_one()
        return f'phone_numbers/{self.sid}/e911_address'

    def _e911_client(self):
        self.ensure_one()
        return self.subproject_id.server_id._get_client()

    def action_assign_e911(self):
        """Assign the chosen (registered) address. The carrier confirms it
        later; until then the status is Pending."""
        for number in self:
            address = number.e911_address_id
            if not address:
                raise UserError(_("Choose the emergency address for %(n)s first.", n=number.name))
            if address.state != 'registered':
                raise UserError(_("Register %(a)s before assigning it.", a=address.name))
            if address.server_id != number.subproject_id.server_id:
                raise UserError(_("%(a)s belongs to a different phone account than %(n)s.",
                                  a=address.name, n=number.name))
            try:
                result = number._e911_client().relay_post(
                    number._e911_path(), e911_address_id=address.remote_id)
            except SignalWireAPIError as exc:
                raise UserError(_("Couldn't assign the emergency address to %(n)s: %(e)s",
                                  n=number.name, e=str(exc))) from exc
            number._e911_apply(result)
        return True

    def action_refresh_e911(self):
        for number in self:
            try:
                result = number._e911_client().relay_get(f'phone_numbers/{number.sid}')
            except SignalWireAPIError as exc:
                raise UserError(_("Couldn't check %(n)s: %(e)s", n=number.name, e=str(exc))) from exc
            number._e911_apply(result)
        return True

    def action_remove_e911(self):
        for number in self.filtered(lambda n: n.e911_status != 'none'):
            try:
                number._e911_client().relay_delete(number._e911_path())
            except SignalWireAPIError as exc:
                raise UserError(_("Couldn't remove the emergency address from %(n)s: %(e)s",
                                  n=number.name, e=str(exc))) from exc
            number._e911_apply({'e911_status': 'pending_removal'})
        return True

    def _e911_apply(self, result):
        """Store the carrier's status and let dependent features react
        (softphones' outbound calling, in signalwire_voip_click2call)."""
        self.ensure_one()
        status = result.get('e911_status') or 'none'
        if status not in dict(E911_STATES):
            status = 'none'
        before = self.e911_status
        self.write({'e911_status': status, 'e911_checked_at': fields.Datetime.now()})
        if before != status:
            self.subproject_id.message_post(body=_(
                "E911 for %(n)s is now %(s)s.", n=self.name, s=dict(E911_STATES)[status]))
            self._on_e911_status_changed()

    def _on_e911_status_changed(self):
        """Hook: override to react when a number's E911 status changes."""
        return True

    @api.model
    def _cron_refresh_e911(self):
        """Pending assignments and removals: the provider sends no notice when
        the carrier confirms, so check them."""
        for number in self.search([('e911_status', 'in', ('pending', 'pending_removal'))]):
            try:
                with self.env.cr.savepoint():
                    number.action_refresh_e911()
            except UserError:
                continue
