# -*- coding: utf-8 -*-
"""Enhanced 911: the street address emergency services are sent to when a
number calls 911.

An address is registered with the phone provider, which has the carrier
validate it, then assigned to each number used at that address. The
number's E911 status goes pending, then active once the carrier confirms;
the provider sends no notice when that happens, so a cron checks pending
numbers. A 911 call from a number with no registered address costs the
account $100 (provider's rule), so outbound calling depends on it (see
signalwire_voip_click2call). US addresses only.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .signalwire_api import SignalWireAPIError

UNIT_TYPES = [
    ("Apartment", "Apartment"), ("Basement", "Basement"), ("Building", "Building"),
    ("Department", "Department"), ("Floor", "Floor"), ("Office", "Office"),
    ("Penthouse", "Penthouse"), ("Suite", "Suite"), ("Trailer", "Trailer"), ("Unit", "Unit"),
]
E911_STATES = [
    ("none", "Not registered"), ("pending", "Pending"), ("active", "Active"),
    ("failed", "Failed"), ("pending_removal", "Being removed"), ("unregistered", "Unregistered"),
]
LABEL_MAX = 32  # the emergency network's limit for the name sent with the call


class SignalWireE911Address(models.Model):
    _name = "signalwire.e911.address"
    _inherit = ["mail.thread"]
    _description = "Emergency Address"
    _order = "name"

    name = fields.Char(
        string="Name for Dispatchers", required=True, tracking=True,
        help="Sent to the 911 dispatcher as the caller's name, e.g. the business "
             "name. 32 characters at most.")
    server_id = fields.Many2one(
        "signalwire.server", string="Phone Account", required=True, ondelete="restrict",
        default=lambda self: self.env["signalwire.server"].search([], limit=1))
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    first_name = fields.Char(required=True)
    last_name = fields.Char(required=True)
    street_number = fields.Char(required=True, help='e.g. "1275"')
    street_name = fields.Char(required=True, help='e.g. "4th St"')
    unit_type = fields.Selection(UNIT_TYPES)
    unit_number = fields.Char()
    city = fields.Char(required=True)
    state_id = fields.Many2one(
        "res.country.state", string="State", required=True,
        domain="[('country_id.code', '=', 'US')]")
    zip = fields.Char(string="ZIP", required=True)
    remote_id = fields.Char(string="Provider ID", readonly=True, copy=False)
    state = fields.Selection(
        [("draft", "Not registered"), ("registered", "Registered"), ("rejected", "Rejected")],
        default="draft", required=True, readonly=True, tracking=True, copy=False)
    validated_at = fields.Datetime(readonly=True, copy=False)
    suggestions = fields.Text(
        readonly=True, copy=False,
        help="Addresses the carrier suggested when it couldn't validate this one.")
    phone_number_ids = fields.One2many("signalwire.phone_number", "e911_address_id", string="Numbers")
    full_address = fields.Char(compute="_compute_full_address")

    @api.depends("street_number", "street_name", "unit_type", "unit_number", "city", "state_id", "zip")
    def _compute_full_address(self):
        for address in self:
            unit = f", {address.unit_type or ''} {address.unit_number or ''}".rstrip(", ") \
                if address.unit_type or address.unit_number else ""
            address.full_address = (
                f"{address.street_number or ''} {address.street_name or ''}{unit}, "
                f"{address.city or ''}, {address.state_id.code or ''} {address.zip or ''}").strip(", ")

    @api.constrains("name")
    def _check_label(self):
        for address in self:
            if len(address.name or "") > LABEL_MAX:
                raise ValidationError(_("The name for dispatchers can be %(n)s characters at most.", n=LABEL_MAX))

    def write(self, vals):
        address_fields = {"street_number", "street_name", "unit_type", "unit_number", "city",
                          "state_id", "zip", "first_name", "last_name", "name"}
        if address_fields & set(vals) and any(a.state == "registered" for a in self):
            raise UserError(_(
                "A registered emergency address can't be edited: the carrier validated it as "
                "it is. Make a new address, register it, and move the numbers to it."))
        return super().write(vals)

    def _payload(self):
        self.ensure_one()
        data = {
            "label": self.name, "country": "US",
            "first_name": self.first_name, "last_name": self.last_name,
            "street_number": self.street_number, "street_name": self.street_name,
            "city": self.city, "state": self.state_id.code, "postal_code": self.zip,
            "emergency_enabled": True, "auto_correct_address": True,
        }
        if self.unit_type:
            data["address_type"] = self.unit_type
        if self.unit_number:
            data["address_number"] = self.unit_number
        return data

    def action_register(self):
        """Register with the phone provider, which validates it with the
        carrier. A rejected address keeps the carrier's suggestions."""
        for address in self:
            if address.state == "registered":
                continue
            try:
                result = address.server_id._get_client().relay_post("addresses", **address._payload())
            except SignalWireAPIError as exc:
                candidates = (exc.payload or {}).get("candidates") or []
                suggestions = "\n".join(
                    f"{c.get('street_number', '')} {c.get('street_name', '')}, {c.get('city', '')}, "
                    f"{c.get('state', '')} {c.get('postal_code', '')}" for c in candidates)
                address.write({"state": "rejected", "suggestions": suggestions or False})
                address.message_post(body=_("The carrier didn't accept this address: %(error)s", error=str(exc)))
                if suggestions:
                    raise UserError(_(
                        "The carrier couldn't validate this address. Did you mean:\n%(s)s\n\nCorrect it "
                        "and register again.", s=suggestions)) from exc
                raise UserError(_("The carrier couldn't validate this address: %(error)s", error=str(exc))) from exc
            if not result.get("emergency_enabled", True):
                raise UserError(_("The provider registered the address but didn't enable 911 for it."))
            address.write({"remote_id": result.get("id"), "state": "registered",
                           "validated_at": fields.Datetime.now(), "suggestions": False})
            address.message_post(body=_("Registered and validated for 911."))
        return True

    def action_reset_rejected(self):
        self.filtered(lambda a: a.state == "rejected").write({"state": "draft"})
