# -*- coding: utf-8 -*-
from odoo import _, api, models, fields
from odoo.exceptions import UserError


class SignalWireSubproject(models.Model):
    """A SignalWire "subproject" (their term for a Twilio-style
    subaccount) provisioned for one resold customer. Subprojects don't
    have their own balance - they **share the parent project's**, per
    SignalWire's own docs (confirmed 2026-09-15) - what they isolate
    is *resources*: a customer's own phone numbers, SIP endpoints,
    calls, and recordings are only visible/manageable within their own
    subproject, not billing. Any customer-facing billing this project
    does has to be tracked and invoiced by Odoo itself.
    """
    _name = 'signalwire.subproject'
    _inherit = ['mail.thread']
    _description = 'SignalWire Subproject'
    _rec_name = 'name'

    name = fields.Char(required=True, tracking=True)
    server_id = fields.Many2one('signalwire.server', required=True, ondelete='restrict')
    partner_id = fields.Many2one('res.partner', tracking=True)
    account_sid = fields.Char(
        string="Account SID", readonly=True, copy=False,
        help="SignalWire's own ID for this subproject, assigned on "
             "provisioning - this is what gets used in place of a "
             "subproject-specific auth token everywhere else in this "
             "module (see signalwire.server's own docstring).")
    state = fields.Selection(
        [('draft', 'Draft'), ('active', 'Active'), ('closed', 'Closed')],
        default='draft', tracking=True, required=True)
    phone_number_ids = fields.One2many('signalwire.phone_number', 'subproject_id')
    active = fields.Boolean(default=True)

    def action_provision(self):
        """Create the actual subproject at SignalWire. One REST call
        (POST /Accounts.json), confirmed live 2026-09-15 to work with
        a plain project token - no special scope needed to create one,
        unlike closing one (see action_close).
        """
        self.ensure_one()
        if self.account_sid:
            raise UserError(_("%(name)s is already provisioned.", name=self.name))
        client = self.server_id._get_client()
        result = client.compat_post('Accounts.json', FriendlyName=self.name)
        self.write({'account_sid': result['sid'], 'state': 'active'})

    def action_close(self):
        """Best-effort close. **Known gap, confirmed live 2026-09-15**:
        POST .../Accounts/{sid}.json with Status=closed did NOT
        actually change the subproject's status when tested - it's
        unclear whether that needs a different token scope or whether
        every resource under it has to be released first. Marks this
        record closed locally either way and logs a note to go verify
        (and finish closing, if needed) in the SignalWire dashboard by
        hand - same category of gap as HestiaCP having no Access Key
        category for package management.
        """
        self.ensure_one()
        if not self.account_sid:
            raise UserError(_("%(name)s was never provisioned.", name=self.name))
        client = self.server_id._get_client()
        client.compat_post(f'Accounts/{self.account_sid}.json', Status='closed')
        self.state = 'closed'
        self.message_post(body=_(
            "Requested closure via the API, but SignalWire's own API did "
            "not confirm this actually took effect when last tested - "
            "double check this subproject's status in the SignalWire "
            "dashboard and close it there by hand if it's still active."))

    def purchase_number(self, phone_number):
        """Buy `phone_number` (an E.164 string from
        signalwire.server.search_available_numbers) into this
        subproject, drawing on the shared project balance for real -
        confirm with the user before calling this against anything
        but a throwaway test, same caution as any other real-money
        action in this project.
        """
        self.ensure_one()
        if self.state != 'active':
            raise UserError(_(
                "%(name)s isn't an active subproject yet.", name=self.name))
        client = self.server_id._get_client()
        result = client.compat_post(
            f'Accounts/{self.account_sid}/IncomingPhoneNumbers.json',
            PhoneNumber=phone_number)
        return self.env['signalwire.phone_number'].create({
            'name': result['phone_number'],
            'sid': result['sid'],
            'subproject_id': self.id,
        })

    def action_open_number_search(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Search Phone Numbers"),
            'res_model': 'signalwire.phone_number.search',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_subproject_id': self.id},
        }
