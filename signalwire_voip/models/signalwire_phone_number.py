# -*- coding: utf-8 -*-
import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .signalwire_api import SignalWireAPIError
from .signalwire_e911 import E911_STATES

_logger = logging.getLogger(__name__)


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

    def _check_not_customer(self):
        """Customer numbers are run from the customer's own Odoo: their
        routing, E911 and caller ID name are changed there, never from here
        (Connect from here would even point their calls at this Odoo)."""
        for number in self:
            if number.number_use == 'customer':
                raise UserError(_(
                    "%(number)s is %(customer)s's number. Change it in their own Odoo.",
                    number=number.name, customer=number.partner_id.name))

    def action_release(self):
        # Not guarded: a customer releases their own number through the
        # portal, which runs here, and billing then ends its contract line.
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
        self._check_not_customer()
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
        self._check_not_customer()
        for number in self:
            try:
                result = number._e911_client().relay_get(f'phone_numbers/{number.sid}')
            except SignalWireAPIError as exc:
                raise UserError(_("Couldn't check %(n)s: %(e)s", n=number.name, e=str(exc))) from exc
            number._e911_apply(result)
        return True

    def action_remove_e911(self):
        self._check_not_customer()
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
    def _cron_refresh_e911_all(self):
        """Daily: ask the provider for every one of our own numbers' E911
        status, not only the pending ones, so a registration made anywhere
        else (the provider's own control panel, another Odoo) shows here.
        Customer numbers are skipped: their sub-account isn't readable from
        this account (404), and their own Odoo manages them."""
        numbers = self.search([('number_use', '=', 'own')])
        for number in numbers:
            try:
                with self.env.cr.savepoint():
                    number.action_refresh_e911()
            except UserError as exc:
                _logger.info("E911 check for %s skipped: %s", number.name, exc)
        numbers._after_e911_refresh_all()

    def _after_e911_refresh_all(self):
        """Hook: after the daily E911 check (outbound rules re-applied in
        signalwire_voip_click2call)."""
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


CNAM_STATES = [
    ('none', "Not requested"), ('pending', "Pending review"), ('in_review', "In review"),
    ('approved', "Approved"), ('rejected', "Rejected"), ('failed', "Failed"),
]
CNAM_MAX = 15
CNAM_ALLOWED = re.compile(r"^[A-Z0-9][A-Z0-9 &'.,-]*$")
TOLL_FREE_PREFIXES = ('+1800', '+1833', '+1844', '+1855', '+1866', '+1877', '+1888')


def normalize_cnam(name):
    """The provider's own normalisation: control characters removed,
    spaces trimmed and collapsed, upper case."""
    name = ''.join(ch for ch in (name or '') if ch.isprintable())
    return ' '.join(name.split()).upper()


def cnam_problem(name):
    """Why the provider would refuse this caller ID name, or None."""
    if not name:
        return _("Enter the caller ID name.")
    if len(name) > CNAM_MAX:
        return _("Caller ID names are at most %(max)s characters, spaces included "
                 "(\"%(name)s\" is %(length)s).", max=CNAM_MAX, name=name, length=len(name))
    if not CNAM_ALLOWED.match(name):
        return _("Caller ID names start with a letter or digit and use only letters, digits, "
                 "spaces and & ' . , -")
    return None


def suggest_cnam(name):
    """A valid suggestion from a company name: normalised, odd characters
    dropped, cut at a word boundary to fit."""
    name = normalize_cnam(re.sub(r"[^A-Za-z0-9 &'.,-]", ' ', name or ''))
    while len(name) > CNAM_MAX and ' ' in name:
        name = name.rsplit(' ', 1)[0]
    # No dangling comma or dash where the cut fell.
    return name[:CNAM_MAX].strip().rstrip(",.-&' ")


class SignalWirePhoneNumberCnam(models.Model):
    """Caller ID name (CNAM): the name people see when this number calls
    them. Requested from the provider per number and reviewed by them;
    shown by US carriers (not on toll-free numbers, not to Canadian
    callers) up to 48 hours after approval. Self-service: each Odoo
    requests it for its own numbers, so nobody processes it by hand."""
    _inherit = 'signalwire.phone_number'

    cnam_name = fields.Char(
        string="Caller ID Name", copy=False,
        help="Up to 15 characters: letters, digits, spaces and & ' . , - "
             "Shown in capitals on the phones of people this number calls.")
    cnam_status = fields.Selection(
        CNAM_STATES, string="Caller ID Name Status", default='none', required=True,
        readonly=True, copy=False)
    cnam_reason = fields.Char(string="Caller ID Name Note", readonly=True, copy=False)
    cnam_checked_at = fields.Datetime(readonly=True, copy=False)
    is_toll_free = fields.Boolean(compute='_compute_is_toll_free')

    @api.depends('name')
    def _compute_is_toll_free(self):
        for number in self:
            number.is_toll_free = (number.name or '').startswith(TOLL_FREE_PREFIXES)

    @api.constrains('cnam_name')
    def _check_cnam_name(self):
        for number in self.filtered('cnam_name'):
            problem = cnam_problem(normalize_cnam(number.cnam_name))
            if problem:
                raise ValidationError(problem)

    @api.onchange('cnam_name')
    def _onchange_cnam_name(self):
        if self.cnam_name:
            self.cnam_name = normalize_cnam(self.cnam_name)

    def _cnam_path(self):
        self.ensure_one()
        return f'phone_numbers/{self.sid}/cnam'

    def action_request_cnam(self):
        """Ask the provider to show this name for each number (the
        number's own name, else one made from the company name)."""
        self._check_not_customer()
        for number in self:
            if number.is_toll_free:
                raise UserError(_("%(n)s is toll-free: carriers don't show caller ID names "
                                  "for toll-free numbers.", n=number.name))
            name = normalize_cnam(number.cnam_name) or suggest_cnam(number.company_id.name)
            problem = cnam_problem(name)
            if problem:
                raise UserError(_("%(n)s: %(problem)s", n=number.name, problem=problem))
            try:
                result = number._e911_client().relay_post(number._cnam_path(), name=name)
            except SignalWireAPIError as exc:
                if exc.status == 422 and 'available' in str(exc):
                    raise UserError(_(
                        "%(n)s's carrier doesn't offer caller ID names. The phone provider's "
                        "support can sometimes arrange it with proof of the business name.",
                        n=number.name)) from exc
                raise UserError(_("Couldn't request the caller ID name for %(n)s: %(e)s",
                                  n=number.name, e=str(exc))) from exc
            number.cnam_name = name
            number._cnam_apply(result)
        return True

    def action_refresh_cnam(self):
        self._check_not_customer()
        for number in self:
            try:
                result = number._e911_client().relay_get(number._cnam_path())
            except SignalWireAPIError as exc:
                if exc.status == 404:
                    result = {'status': 'none'}
                else:
                    raise UserError(_("Couldn't check %(n)s: %(e)s", n=number.name, e=str(exc))) from exc
            number._cnam_apply(result)
        return True

    def _cnam_apply(self, result):
        self.ensure_one()
        status = result.get('status') or 'none'
        if status not in dict(CNAM_STATES):
            status = 'none'
        reason = result.get('reason') or result.get('required_action') or False
        before = self.cnam_status
        self.write({'cnam_status': status, 'cnam_reason': reason,
                    'cnam_checked_at': fields.Datetime.now()})
        if before != status and status != 'none':
            self.subproject_id.message_post(body=_(
                "Caller ID name \"%(name)s\" for %(n)s: %(s)s%(why)s.", name=self.cnam_name or '',
                n=self.name, s=dict(CNAM_STATES)[status],
                why=f" ({reason})" if reason else ''))

    @api.model
    def _cron_refresh_cnam(self):
        """Requests waiting for the provider's review: check until decided."""
        for number in self.search([('cnam_status', 'in', ('pending', 'in_review')),
                                   ('number_use', '=', 'own')]):
            try:
                with self.env.cr.savepoint():
                    number.action_refresh_cnam()
            except UserError:
                continue

