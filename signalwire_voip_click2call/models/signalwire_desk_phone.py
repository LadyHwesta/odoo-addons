# -*- coding: utf-8 -*-
import re
import secrets

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

MAC_RE = re.compile(r'^[0-9a-f]{12}$')


class SignalWireDeskPhone(models.Model):
    """A physical SIP desk phone registered to a user's own extension -
    a separate SignalWire SIP Endpoint per device (not a second
    registration on the user's own softphone endpoint), so it rings
    alongside the softphone via the existing multi-target <Dial>
    mechanism instead of relying on unconfirmed multi-registration
    behavior on a single endpoint. See this module's README for the
    live SIP-over-UDP verification this is built on.
    """
    _name = 'signalwire.desk_phone'
    _description = 'SignalWire Desk Phone'
    _order = 'name'

    _mac_address_unique = models.Constraint(
        'unique(mac_address)',
        "A phone with this MAC address is already registered.",
    )

    user_id = fields.Many2one('res.users', required=True, ondelete='cascade')
    name = fields.Char(required=True, help='e.g. "Front Desk", "Conference Room"')
    mac_address = fields.Char(
        required=True,
        help="The phone's MAC address, in any common format "
             "(aa:bb:cc:dd:ee:ff, aa-bb-..., or plain) - normalized "
             "automatically.")
    brand = fields.Selection(
        [('yealink', 'Yealink'), ('grandstream', 'Grandstream')], required=True)

    signalwire_sip_endpoint_id = fields.Char(
        string="SignalWire SIP Endpoint ID", copy=False,
        help="SignalWire's own ID for this phone's SIP Endpoint - "
             "needed to release it later. Set automatically by "
             "\"Provision\", not editable by hand.")
    signalwire_server_id = fields.Many2one('signalwire.server', copy=False)
    voip_username = fields.Char(copy=False)
    voip_password = fields.Char(copy=False)

    provisioning_url = fields.Char(
        compute='_compute_provisioning_url',
        help="Point this phone's Auto Provisioning Server URL at this "
             "(or, for a whole office at once, point a DHCP scope's "
             "option 66 at this URL's own directory - the phone "
             "appends its own filename automatically).")

    @api.depends('mac_address', 'brand', 'signalwire_sip_endpoint_id')
    def _compute_provisioning_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        for phone in self:
            if not phone.signalwire_sip_endpoint_id or not phone.mac_address:
                phone.provisioning_url = False
                continue
            phone.provisioning_url = f'{base_url}{phone._provisioning_path()}'

    def _provisioning_path(self):
        self.ensure_one()
        mac = self.mac_address
        if self.brand == 'yealink':
            return f'/signalwire/provisioning/{mac}.cfg'
        if self.brand == 'grandstream':
            return f'/signalwire/provisioning/cfg{mac}.xml'
        return False

    @api.constrains('mac_address')
    def _check_mac_address(self):
        for phone in self:
            if not MAC_RE.match(phone.mac_address or ''):
                raise ValidationError(_(
                    "%(mac)s isn't a valid MAC address - expected 12 hex "
                    "digits (colons/dashes are fine, e.g. "
                    "aa:bb:cc:dd:ee:ff).", mac=phone.mac_address))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('mac_address'):
                vals['mac_address'] = self._normalize_mac(vals['mac_address'])
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('mac_address'):
            vals['mac_address'] = self._normalize_mac(vals['mac_address'])
        return super().write(vals)

    @staticmethod
    def _normalize_mac(mac_address):
        return re.sub(r'[^0-9a-fA-F]', '', mac_address or '').lower()

    def action_provision(self):
        """Same SignalWire call as res.users.action_provision_signalwire_sip
        - a dedicated SIP Endpoint for this device - just scoped to
        this record instead of a user.
        """
        self.ensure_one()
        if self.signalwire_sip_endpoint_id:
            raise UserError(_(
                "%(name)s is already provisioned.", name=self.name))
        server = self.env['signalwire.server'].search([], limit=1)
        if not server:
            raise UserError(_("No SignalWire project is configured yet."))

        username = f'deskphone{self.id}'
        password = secrets.token_urlsafe(18)
        result = server._get_client().relay_post(
            'endpoints/sip', username=username, password=password)

        self.write({
            'signalwire_sip_endpoint_id': result['id'],
            'signalwire_server_id': server.id,
            'voip_username': result['username'],
            'voip_password': password,
        })

    def action_release(self):
        self.ensure_one()
        if not self.signalwire_sip_endpoint_id:
            raise UserError(_(
                "%(name)s has no SignalWire endpoint provisioned.", name=self.name))
        self.signalwire_server_id._get_client().relay_delete(
            f'endpoints/sip/{self.signalwire_sip_endpoint_id}')
        self.write({
            'signalwire_sip_endpoint_id': False,
            'signalwire_server_id': False,
            'voip_username': False,
            'voip_password': False,
        })
