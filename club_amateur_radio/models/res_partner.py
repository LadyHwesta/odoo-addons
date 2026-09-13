# -*- coding: utf-8 -*-
import logging
import time
from datetime import timedelta

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

# Cron politeness: callook.info is a free, volunteer-run service. Pause
# between lookups and cap how many one nightly sweep will do.
CRON_LOOKUP_PAUSE = 0.4
CRON_LOOKUP_LIMIT = 1000

# Prefix of the To-Do the expiry sweep raises. Also how it recognises one it
# already raised, so a member never collects a second.
_EXPIRY_ACTIVITY_PREFIX = "Amateur radio licence expires"


class ResPartner(models.Model):
    _inherit = "res.partner"

    callsign = fields.Char(
        string="Call Sign", index="btree_not_null", tracking=True,
        help="FCC amateur radio call sign. Uppercased automatically.")
    gmrs_callsign = fields.Char(
        string="GMRS Call Sign", index="btree_not_null",
        help="FCC General Mobile Radio Service call sign - a separate "
             "licence from amateur radio, tracked here since the club "
             "does too. Uppercased automatically.")
    ham_license_class = fields.Selection(
        selection=[
            ("novice", "Novice"),
            ("technician", "Technician"),
            ("technician_plus", "Technician Plus"),
            ("general", "General"),
            ("advanced", "Advanced"),
            ("extra", "Amateur Extra"),
        ],
        string="Operator Class")
    ham_license_type = fields.Selection(
        selection=[
            ("person", "Individual"),
            ("club", "Club Station"),
            ("military", "Military Recreation"),
            ("races", "RACES"),
            ("recreation", "Recreation"),
        ],
        string="Licence Type")
    ham_license_grant_date = fields.Date(string="Licence Granted")
    ham_license_expiry_date = fields.Date(string="Licence Expires", tracking=True)
    ham_frn = fields.Char(
        string="FRN", help="FCC Registration Number.")
    ham_grid_square = fields.Char(
        string="Grid Square", help="Maidenhead locator, from the FCC address.")
    ham_trustee_name = fields.Char(
        string="Trustee", help="For a club station licence: the licence trustee.")
    ham_trustee_callsign = fields.Char(string="Trustee Call Sign")
    arrl_member = fields.Boolean(string="ARRL Member")
    ham_license_last_checked = fields.Datetime(
        string="Licence Last Checked", readonly=True,
        help="When this licence was last refreshed from the FCC ULS.")
    ham_license_expiring_soon = fields.Boolean(
        string="Licence Expiring Soon", compute="_compute_ham_license_expiring_soon",
        store=True,
        help="The FCC licence has expired or expires within the warning "
             "window set in Settings.")

    # ------------------------------------------------------------------
    @api.model
    def _ham_license_warn_days(self):
        param = self.env["ir.config_parameter"].sudo().get_param(
            "club_amateur_radio.license_warn_days", "60")
        try:
            return max(int(param), 0)
        except (TypeError, ValueError):
            return 60

    @api.depends("ham_license_expiry_date")
    def _compute_ham_license_expiring_soon(self):
        horizon = fields.Date.context_today(self) + timedelta(
            days=self._ham_license_warn_days())
        for partner in self:
            partner.ham_license_expiring_soon = bool(
                partner.ham_license_expiry_date
                and partner.ham_license_expiry_date <= horizon
            )

    # ------------------------------------------------------------------
    # Call-sign normalisation
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("callsign"):
                vals["callsign"] = vals["callsign"].strip().upper()
            if vals.get("gmrs_callsign"):
                vals["gmrs_callsign"] = vals["gmrs_callsign"].strip().upper()
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("callsign"):
            vals["callsign"] = vals["callsign"].strip().upper()
        if vals.get("gmrs_callsign"):
            vals["gmrs_callsign"] = vals["gmrs_callsign"].strip().upper()
        return super().write(vals)

    @api.onchange("callsign")
    def _onchange_callsign_upper(self):
        if self.callsign:
            self.callsign = self.callsign.strip().upper()

    @api.onchange("gmrs_callsign")
    def _onchange_gmrs_callsign_upper(self):
        if self.gmrs_callsign:
            self.gmrs_callsign = self.gmrs_callsign.strip().upper()

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------
    def action_lookup_callsign(self):
        """Form button: refresh this member's licence from the FCC and fill
        blank name / address fields from it."""
        self.ensure_one()
        data = self.env["club.uls.lookup"].lookup(self.callsign)
        self._ham_apply_uls_data(data, fill_contact=True)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "title": _("Call sign found"),
                "message": _(
                    "%(callsign)s - %(cls)s, licence expires %(exp)s.",
                    callsign=self.callsign,
                    cls=dict(self._fields["ham_license_class"].selection).get(
                        self.ham_license_class, _("n/a")),
                    exp=self.ham_license_expiry_date or _("n/a"),
                ),
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def _ham_apply_uls_data(self, data, fill_contact=False):
        """Write normalised ULS ``data`` (see ``club.uls.lookup._parse``)
        onto this partner. Licence fields are always refreshed (the FCC is
        authoritative); name / address are only filled when ``fill_contact``
        is set *and* the field is currently blank."""
        self.ensure_one()
        vals = {
            "ham_license_class": data.get("license_class"),
            "ham_license_type": data.get("license_type"),
            "ham_license_grant_date": data.get("grant_date"),
            "ham_license_expiry_date": data.get("expiry_date"),
            "ham_frn": data.get("frn"),
            "ham_grid_square": data.get("grid_square"),
            "ham_trustee_name": data.get("trustee_name"),
            "ham_trustee_callsign": data.get("trustee_callsign"),
            "ham_license_last_checked": fields.Datetime.now(),
        }
        if data.get("callsign"):
            vals["callsign"] = data["callsign"]

        if fill_contact:
            if not self.name and data.get("licensee_name"):
                vals["name"] = data["licensee_name"]
            if not self.street and data.get("street"):
                vals["street"] = data["street"]
            if not self.street2 and data.get("street2"):
                vals["street2"] = data["street2"]
            if not self.city and data.get("city"):
                vals["city"] = data["city"]
            if not self.zip and data.get("zip"):
                vals["zip"] = data["zip"]
            if not self.country_id and data.get("state_code"):
                vals["country_id"] = self.env.ref("base.us").id
            if not self.state_id and data.get("state_code"):
                country = self.country_id or self.env.ref("base.us")
                state = self.env["res.country.state"].search([
                    ("country_id", "=", country.id),
                    ("code", "=", data["state_code"]),
                ], limit=1)
                if state:
                    vals["state_id"] = state.id

        self.write({k: v for k, v in vals.items() if v is not None})

    # ------------------------------------------------------------------
    # Nightly refresh + expiry activities
    # ------------------------------------------------------------------
    @api.model
    def _cron_refresh_ham_licenses(self):
        Lookup = self.env["club.uls.lookup"]
        if not Lookup._enabled():
            _logger.info("club_amateur_radio: ULS lookup disabled, skipping refresh")
            return
        partners = self.search(
            [("callsign", "!=", False)], limit=CRON_LOOKUP_LIMIT)
        for partner in partners:
            try:
                data = Lookup.lookup(partner.callsign)
            except Exception:  # noqa: BLE001 - one bad call sign must not
                # stop the sweep; UserError included (e.g. licence lapsed).
                _logger.info(
                    "club_amateur_radio: ULS refresh failed for %s",
                    partner.callsign, exc_info=True)
                partner.ham_license_last_checked = fields.Datetime.now()
                continue
            partner._ham_apply_uls_data(data, fill_contact=False)
            time.sleep(CRON_LOOKUP_PAUSE)
        partners._ham_raise_expiry_activities()

    def _ham_raise_expiry_activities(self):
        """Raise a single To-Do per member whose licence is expiring soon and
        doesn't already carry one (recognised by its summary prefix)."""
        for partner in self.filtered("ham_license_expiring_soon"):
            already = partner.activity_ids.filtered(
                lambda a: (a.summary or "").startswith(_EXPIRY_ACTIVITY_PREFIX))
            if already:
                continue
            partner.activity_schedule(
                "mail.mail_activity_data_todo",
                date_deadline=partner.ham_license_expiry_date,
                summary=_(
                    "%(prefix)s %(date)s",
                    prefix=_EXPIRY_ACTIVITY_PREFIX,
                    date=partner.ham_license_expiry_date or "",
                ),
                note=_(
                    "%(name)s's FCC licence (%(callsign)s) expires on "
                    "%(date)s. Nudge them to renew at fcc.gov before it lapses.",
                    name=partner.display_name,
                    callsign=partner.callsign or "",
                    date=partner.ham_license_expiry_date or "",
                ),
            )
