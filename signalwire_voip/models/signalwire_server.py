# -*- coding: utf-8 -*-
import logging
import re
from datetime import timedelta

from odoo import _, api, models, fields
from odoo.exceptions import UserError, ValidationError

from .. import webhook_security
from .signalwire_api import SignalWireAPIError, SignalWireClient

_logger = logging.getLogger(__name__)

# Our names -> the Relay REST search's number_type values.
NUMBER_TYPES = {'local': 'local', 'toll_free': 'tollfree'}
MATCH_TYPES = ('starts_with', 'contains', 'ends_with')
TOLL_FREE_SMALL_LIMIT = 10
KEYPAD = {letter: digit for digit, letters in {
    '2': 'ABC', '3': 'DEF', '4': 'GHI', '5': 'JKL',
    '6': 'MNO', '7': 'PQRS', '8': 'TUV', '9': 'WXYZ'}.items() for letter in letters}


def letters_to_digits(text):
    """'BEAR-1' -> '23271': letters become
    their phone keypad digits, spaces and dashes are dropped. Anything
    else is refused rather than silently ignored."""
    digits = []
    for char in text.upper():
        if char.isdigit():
            digits.append(char)
        elif char in KEYPAD:
            digits.append(KEYPAD[char])
        elif char not in ' -':
            raise UserError(_("Use only digits and letters to search for."))
    return ''.join(digits)


class SignalWireServer(models.Model):
    """One SignalWire project's connection settings. In practice
    there's a single one of these for the business - it's the parent
    project whose credentials manage every resold customer's
    subproject too (see signalwire.subproject), since a subproject's
    own auth token can't actually be retrieved via the API (confirmed
    live 2026-09-15 - it comes back masked) but isn't needed anyway.
    """
    _name = 'signalwire.server'
    _description = 'SignalWire Project'

    name = fields.Char(required=True, default='SignalWire')
    space = fields.Char(
        string="Space Domain", required=True, groups="base.group_system",
        help='Your SignalWire Space domain, e.g. '
             '"example.signalwire.com" - no "https://" prefix.')
    project_id = fields.Char(
        string="Project ID", required=True, groups="base.group_system",
        help="Settings -> API in your SignalWire dashboard.")
    api_token = fields.Char(
        string="API Token", required=True, groups="base.group_system",
        help="Generated alongside the Project ID. Needs at least the "
             "Voice and Numbers scopes for everything this module "
             "does; Messaging too once signalwire_sms is installed.")
    active = fields.Boolean(default=True)

    signing_key = fields.Char(
        string="Signing Key", groups="base.group_system", copy=False,
        help="SignalWire Dashboard > API Credentials > Signing Key (Show). "
             "Not the API token. Used to check that calls and texts reported "
             "to this Odoo really come from SignalWire. Subprojects have "
             "their own Signing Keys: add those on each subproject.")
    webhook_signature_mode = fields.Selection(
        [('off', "Off"), ('log', "Check and log only"), ('enforce', "Reject unsigned")],
        string="Webhook Signatures", default='log', required=True,
        groups="base.group_system",
        help="Check and log only: every webhook is checked and any failure is "
             "logged, but nothing is refused - use this until the log shows "
             "they all pass. Reject unsigned: webhooks without a valid "
             "signature get a 403 and are ignored.")
    webhook_last_valid = fields.Datetime(
        string="Last Valid Webhook", readonly=True, groups="base.group_system")
    webhook_last_invalid = fields.Datetime(
        string="Last Failed Webhook", readonly=True, groups="base.group_system")
    webhook_last_invalid_path = fields.Char(
        string="Failed Webhook Address", readonly=True, groups="base.group_system")

    @api.constrains('webhook_signature_mode', 'signing_key')
    def _check_signature_mode(self):
        for server in self:
            if server.webhook_signature_mode == 'enforce' and not server.signing_key:
                raise ValidationError(_(
                    "Add the Signing Key before rejecting unsigned webhooks, or "
                    "every call and text would be refused."))

    @api.model
    def _check_webhook_signature(self, httprequest):
        """True when this webhook may be handled. See webhook_security."""
        servers = self.sudo().search([])
        modes = set(servers.mapped('webhook_signature_mode'))
        mode = 'enforce' if 'enforce' in modes else 'log' if 'log' in modes else 'off'
        if mode == 'off':
            return True
        keys = [k for k in servers.mapped('signing_key') if k]
        keys += [k for k in self.env['signalwire.subproject'].sudo().search([]).mapped('signing_key') if k]
        if not keys:
            _logger.info("SignalWire webhook %s not checked: no Signing Key set yet.", httprequest.path)
            return True
        base_url = (self.env['ir.config_parameter'].sudo().get_param('web.base.url') or '').rstrip('/')
        query = httprequest.query_string.decode()
        path = httprequest.path + (f'?{query}' if query else '')
        urls = [base_url + path, httprequest.url]
        valid = webhook_security.is_valid(
            keys, httprequest.headers.get(webhook_security.HEADER, ''),
            urls, list(httprequest.form.items(multi=True)))
        now = fields.Datetime.now()
        target = servers[:1]
        if valid:
            if not target.webhook_last_valid or now - target.webhook_last_valid > timedelta(minutes=10):
                target.webhook_last_valid = now
            return True
        _logger.warning("SignalWire webhook %s failed the signature check (%s).", httprequest.path,
                        "rejected" if mode == 'enforce' else "allowed: log-only mode")
        target.write({'webhook_last_invalid': now, 'webhook_last_invalid_path': httprequest.path})
        return mode != 'enforce'

    def _get_client(self):
        self.ensure_one()
        return SignalWireClient(
            space=self.space, project_id=self.project_id, api_token=self.api_token)

    def action_test_connection(self):
        self.ensure_one()
        client = self._get_client()
        result = client.compat_get(f'Accounts/{self.project_id}.json')
        raise UserError(_(
            "Connected. Project status: %(status)s.",
            status=result.get('status', '?')))

    def action_import_numbers(self):
        """Load the numbers this project already owns - for an Odoo
        connected to a subproject someone else provisioned (a hosted
        customer's own database, with a token scoped to their
        subproject), where nothing was bought from here. Records this
        project itself as a subproject (never creating anything at
        SignalWire) and adds each number not loaded yet. Safe to run
        again."""
        self.ensure_one()
        Subproject = self.env['signalwire.subproject']
        own = Subproject.with_context(active_test=False).search(
            [('server_id', '=', self.id), ('account_sid', '=', self.project_id)], limit=1)
        if not own:
            own = Subproject.create({
                'name': self.name, 'server_id': self.id,
                'account_sid': self.project_id, 'state': 'active',
            })
        result = self._get_client().compat_get(
            f'Accounts/{self.project_id}/IncomingPhoneNumbers.json', PageSize=1000)
        Number = self.env['signalwire.phone_number'].with_context(active_test=False)
        known = set(Number.search([('subproject_id', '=', own.id)]).mapped('sid'))
        new = [
            {'name': n['phone_number'], 'sid': n['sid'], 'subproject_id': own.id}
            for n in result.get('incoming_phone_numbers', [])
            if n.get('sid') and n['sid'] not in known
        ]
        Number.create(new)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Numbers imported"),
                'message': _(
                    "%(new)s new, %(known)s already here. Open each one under "
                    "Phone Numbers to choose who it rings and connect it.",
                    new=len(new), known=len(known)),
                'type': 'success',
                'sticky': False,
            },
        }

    def search_numbers(self, number_type='local', match='contains', pattern=None,
                       area_code=None, region=None, city=None, max_results=50):
        """Numbers available to buy, with where they are and what they
        can do, through the Relay REST search SignalWire's own
        dashboard uses (``phone_numbers/search``). Free; nothing is
        reserved by looking.

        :param number_type: ``'local'`` or ``'toll_free'``.
        :param match: ``'starts_with'``, ``'contains'`` or
            ``'ends_with'``, applied to `pattern`. SignalWire takes one
            of the three at a time.
        :param pattern: 3 to 7 digits; letters are turned into their
            keypad digits (BEAR -> 2327), spaces and dashes dropped.
        :param area_code, region, city: local numbers only. `region` is
            a two-letter state/province code; `city` needs `region`.
        :returns: a list of dicts with ``e164``, ``national``,
            ``region``, ``rate_center`` (the nearest thing to a city
            SignalWire gives) and ``capabilities`` (e.g. ``['voice']``;
            SMS/MMS only appear once this project is cleared for
            messaging, so they say little about what a buyer gets).
        """
        self.ensure_one()
        if number_type not in NUMBER_TYPES:
            raise UserError(_("Unknown number type: %(type)s", type=number_type))
        params = {'number_type': NUMBER_TYPES[number_type], 'max_results': max_results}

        digits = letters_to_digits(pattern or '')
        if digits:
            if match not in MATCH_TYPES:
                raise UserError(_("Choose starts with, contains or ends with."))
            if not 3 <= len(digits) <= 7:
                raise UserError(_("Use 3 to 7 digits or letters to search for."))
            params[match] = digits

        area_code = (area_code or '').strip()
        region = (region or '').strip().upper()
        city = (city or '').strip()
        if number_type == 'toll_free' and (area_code or region or city):
            raise UserError(_("Toll-free numbers can't be searched by area code or place."))
        if area_code:
            if not re.fullmatch(r'[2-9]\d\d', area_code):
                raise UserError(_("An area code is 3 digits and doesn't start with 0 or 1."))
            params['areacode'] = area_code
        if city and not region:
            raise UserError(_("Choose a state before a city."))
        if region:
            if not re.fullmatch(r'[A-Z]{2}', region):
                raise UserError(_("Use the two-letter state code, like CA."))
            params['region'] = region
        if city:
            params['city'] = city

        client = self._get_client()
        try:
            result = client.relay_get('phone_numbers/search', **params)
        except SignalWireAPIError:
            # Some Spaces cap toll-free searches at 10 results and refuse
            # a bigger max_results outright; ask again within the cap.
            if number_type != 'toll_free' or max_results <= TOLL_FREE_SMALL_LIMIT:
                raise
            params['max_results'] = TOLL_FREE_SMALL_LIMIT
            result = client.relay_get('phone_numbers/search', **params)
        return [{
            'e164': n['e164'],
            'national': n.get('national_number_formatted') or n['e164'],
            'region': n.get('region') or '',
            'rate_center': n.get('rate_center') or '',
            'capabilities': n.get('capabilities') or [],
        } for n in result.get('data', []) if n.get('e164')]

    def search_available_numbers(self, account_sid, country, area_code=None):
        """Numbers available to purchase within the subproject
        `account_sid`, as a list of E.164 strings. Search is free -
        nothing is reserved or charged by looking. The older,
        Compatibility API search: area code only. ``search_numbers``
        does more and is what this module's own screens use.

        :param country: ISO country code SignalWire recognizes for
            number search, e.g. "US" or "CA" - not validated here,
            SignalWire's own error surfaces a bad one.
        :param area_code: optional, narrows results (US/CA only).
        """
        self.ensure_one()
        client = self._get_client()
        params = {'AreaCode': area_code} if area_code else {}
        result = client.compat_get(
            f'Accounts/{account_sid}/AvailablePhoneNumbers/{country}/Local.json',
            **params)
        return [n['phone_number'] for n in result.get('available_phone_numbers', [])]
