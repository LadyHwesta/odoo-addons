# -*- coding: utf-8 -*-
"""FCC ULS call-sign lookup, via the free callook.info JSON API.

callook.info wraps the FCC Universal Licensing System amateur database and
serves it as JSON at ``https://callook.info/<callsign>/json`` - no API key,
US amateur licences only, call-sign data being public record. A valid
response looks like::

    {"status": "VALID", "type": "PERSON",
     "current": {"callsign": "...", "operClass": "EXTRA"},
     "trustee": {"callsign": "", "name": ""},
     "name": "LAST, FIRST M",
     "address": {"line1": "123 MAIN ST", "line2": "TOWN, ST 01234", "attn": "..."},
     "location": {"gridsquare": "FN31pr", ...},
     "otherInfo": {"grantDate": "MM/DD/YYYY", "expiryDate": "MM/DD/YYYY",
                   "frn": "0001234567", ...}}

Anything other than ``status == "VALID"`` (``INVALID`` / ``UPDATING``)
returns only the ``status`` key.

The HTTP shape here mirrors ``activitypub``'s ``fetch_json``: a tight
(connect, read) timeout, a streamed size cap, and every failure surfaced as
one clean error rather than leaking a ``requests`` exception. callook.info
is a fixed public host, so the SSRF address check that module needs is not
repeated here; the base URL is overridable (system parameter
``club_amateur_radio.callook_base_url``) so tests can point it at a stub.
"""
import json
import logging
import re
from datetime import datetime

import requests

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://callook.info"
HTTP_TIMEOUT = (5, 15)
MAX_RESPONSE_BYTES = 256 * 1024
USER_AGENT = "Odoo-club-amateur-radio (+https://github.com/LadyHwesta/odoo-addons)"

# callook.info operClass string -> our stored selection value.
OPER_CLASS_MAP = {
    "NOVICE": "novice",
    "TECHNICIAN": "technician",
    "TECHNICIAN PLUS": "technician_plus",
    "GENERAL": "general",
    "ADVANCED": "advanced",
    "EXTRA": "extra",
}
# callook.info type string -> our stored selection value.
LICENSE_TYPE_MAP = {
    "PERSON": "person",
    "CLUB": "club",
    "MILITARY": "military",
    "RACES": "races",
    "RECREATION": "recreation",
}
# "TOWN, ST 01234" or "TOWN, ST 01234-5678"
_CITY_STATE_ZIP_RE = re.compile(
    r"^\s*(?P<city>.+?),\s*(?P<state>[A-Za-z]{2})\s+(?P<zip>\d{5}(?:-\d{4})?)\s*$"
)


class ClubUlsLookup(models.AbstractModel):
    _name = "club.uls.lookup"
    _description = "FCC ULS Call-sign Lookup Service"

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------
    @api.model
    def _enabled(self):
        param = self.env["ir.config_parameter"].sudo().get_param(
            "club_amateur_radio.uls_lookup_enabled", "True"
        )
        return str(param).strip().lower() not in ("false", "0", "")

    @api.model
    def _base_url(self):
        param = self.env["ir.config_parameter"].sudo().get_param(
            "club_amateur_radio.callook_base_url"
        )
        return (param or DEFAULT_BASE_URL).rstrip("/")

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------
    @api.model
    def lookup(self, callsign):
        """Return a normalised dict of licence data for ``callsign``.

        Raises :class:`~odoo.exceptions.UserError` when lookup is disabled,
        the call sign is blank, the service can't be reached, or the FCC has
        no active licence for it.
        """
        callsign = (callsign or "").strip().upper()
        if not callsign:
            raise UserError(_("Enter a call sign first."))
        if not self._enabled():
            raise UserError(_(
                "FCC call-sign lookup is turned off "
                "(Settings > Amateur Radio Club)."
            ))
        payload = self._fetch(callsign)
        status = payload.get("status")
        if status == "UPDATING":
            raise UserError(_(
                "The FCC record for %s is mid-update; try again shortly.", callsign
            ))
        if status != "VALID":
            raise UserError(_("No active FCC licence found for %s.", callsign))
        return self._parse(payload)

    @api.model
    def _fetch(self, callsign):
        """Do the HTTP GET and return the parsed JSON body (a dict)."""
        url = "%s/%s/json" % (self._base_url(), callsign)
        try:
            resp = requests.get(
                url,
                timeout=HTTP_TIMEOUT,
                stream=True,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            )
            resp.raise_for_status()
            raw = self._read_capped(resp)
        except requests.RequestException as exc:
            _logger.info("callook.info lookup failed for %s: %s", callsign, exc)
            raise UserError(_(
                "Could not reach the FCC call-sign lookup service. %s", exc
            )) from exc
        try:
            payload = json.loads(raw)
        except ValueError as exc:
            raise UserError(_(
                "The FCC call-sign lookup service returned an unreadable response."
            )) from exc
        if not isinstance(payload, dict):
            raise UserError(_(
                "The FCC call-sign lookup service returned an unexpected response."
            ))
        return payload

    @staticmethod
    def _read_capped(resp):
        chunks, total = [], 0
        for chunk in resp.iter_content(8192):
            total += len(chunk)
            if total > MAX_RESPONSE_BYTES:
                resp.close()
                raise UserError(_(
                    "The FCC call-sign lookup service returned an oversized response."
                ))
            chunks.append(chunk)
        resp.close()
        return b"".join(chunks)

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------
    @api.model
    def _parse(self, payload):
        current = payload.get("current") or {}
        trustee = payload.get("trustee") or {}
        address = payload.get("address") or {}
        location = payload.get("location") or {}
        other = payload.get("otherInfo") or {}

        vals = {
            "callsign": (current.get("callsign") or "").strip().upper() or False,
            "license_class": OPER_CLASS_MAP.get(
                (current.get("operClass") or "").strip().upper()
            ) or False,
            "license_type": LICENSE_TYPE_MAP.get(
                (payload.get("type") or "").strip().upper()
            ) or False,
            "grant_date": self._parse_date(other.get("grantDate")),
            "expiry_date": self._parse_date(other.get("expiryDate")),
            "frn": (other.get("frn") or "").strip() or False,
            "grid_square": (location.get("gridsquare") or "").strip() or False,
            "trustee_name": (trustee.get("name") or "").strip() or False,
            "trustee_callsign": (trustee.get("callsign") or "").strip().upper() or False,
            "licensee_name": self._humanise_name(payload.get("name")),
            "street": (address.get("line1") or "").strip() or False,
            "street2": self._strip_attn(address.get("attn")),
            "city": False,
            "state_code": False,
            "zip": False,
        }
        match = _CITY_STATE_ZIP_RE.match(address.get("line2") or "")
        if match:
            vals["city"] = match.group("city").strip().title()
            vals["state_code"] = match.group("state").upper()
            vals["zip"] = match.group("zip")
        return vals

    @staticmethod
    def _parse_date(value):
        value = (value or "").strip()
        if not value:
            return False
        try:
            return datetime.strptime(value, "%m/%d/%Y").date()
        except ValueError:
            return False

    @staticmethod
    def _strip_attn(value):
        value = (value or "").strip()
        if not value:
            return False
        return re.sub(r"^attn:?\s*", "", value, flags=re.IGNORECASE).strip() or False

    @staticmethod
    def _humanise_name(value):
        """FCC stores a person's name as ``"LAST, FIRST M"`` - flip it to
        ``"First M Last"`` and title-case it. A club name has no comma; just
        title-case it. Returns ``False`` for an empty input."""
        value = (value or "").strip()
        if not value:
            return False
        if "," in value:
            last, rest = value.split(",", 1)
            value = "%s %s" % (rest.strip(), last.strip())
        return " ".join(part.capitalize() for part in value.split())
