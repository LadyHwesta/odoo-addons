# -*- coding: utf-8 -*-
from datetime import date, timedelta
from unittest.mock import patch

import requests

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

# A realistic individual-licence callook.info payload.
PERSON_PAYLOAD = {
    "status": "VALID",
    "type": "PERSON",
    "current": {"callsign": "K1ABC", "operClass": "EXTRA"},
    "previous": {"callsign": "", "operClass": ""},
    "trustee": {"callsign": "", "name": ""},
    "name": "DOE, JANE Q",
    "address": {
        "line1": "42 OAK LN",
        "line2": "SPRINGFIELD, MA 01101",
        "attn": "ATTN:  Jane Q Doe",
    },
    "location": {"latitude": "42.1", "longitude": "-72.5", "gridsquare": "FN32ab"},
    "otherInfo": {
        "grantDate": "03/15/2019",
        "expiryDate": "03/15/2029",
        "lastActionDate": "03/15/2019",
        "frn": "0009998887",
        "ulsUrl": "https://wireless2.fcc.gov/x",
    },
}

# A real club-station payload (W1AW), operClass empty, trustee populated.
CLUB_PAYLOAD = {
    "status": "VALID",
    "type": "CLUB",
    "current": {"callsign": "W1AW", "operClass": ""},
    "previous": {"callsign": "", "operClass": ""},
    "trustee": {"callsign": "NA2AA", "name": "Minster, David A"},
    "name": "ARRL HQ OPERATORS CLUB",
    "address": {
        "line1": "225 MAIN ST",
        "line2": "NEWINGTON, CT 06111",
        "attn": "ATTN:  David A Minster",
    },
    "location": {"gridsquare": "FN31pr"},
    "otherInfo": {
        "grantDate": "12/08/2020",
        "expiryDate": "02/26/2031",
        "frn": "0004511143",
        "ulsUrl": "https://wireless2.fcc.gov/y",
    },
}


def _fake_fetch(payload):
    def _fetch(self, callsign):
        return payload
    return _fetch


@tagged("post_install", "-at_install")
class TestUlsLookup(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Lookup = cls.env["club.uls.lookup"]
        cls.LookupCls = type(cls.Lookup)

    # ------------------------------------------------------------------
    # _parse
    # ------------------------------------------------------------------
    def test_parse_person(self):
        vals = self.Lookup._parse(PERSON_PAYLOAD)
        self.assertEqual(vals["callsign"], "K1ABC")
        self.assertEqual(vals["license_class"], "extra")
        self.assertEqual(vals["license_type"], "person")
        self.assertEqual(vals["grant_date"], date(2019, 3, 15))
        self.assertEqual(vals["expiry_date"], date(2029, 3, 15))
        self.assertEqual(vals["frn"], "0009998887")
        self.assertEqual(vals["grid_square"], "FN32ab")
        self.assertEqual(vals["licensee_name"], "Jane Q Doe")
        self.assertEqual(vals["street"], "42 OAK LN")
        self.assertEqual(vals["street2"], "Jane Q Doe")
        self.assertEqual(vals["city"], "Springfield")
        self.assertEqual(vals["state_code"], "MA")
        self.assertEqual(vals["zip"], "01101")

    def test_parse_club(self):
        vals = self.Lookup._parse(CLUB_PAYLOAD)
        self.assertEqual(vals["license_type"], "club")
        self.assertFalse(vals["license_class"], "club stations have no operator class")
        self.assertEqual(vals["trustee_name"], "Minster, David A")
        self.assertEqual(vals["trustee_callsign"], "NA2AA")
        self.assertEqual(vals["expiry_date"], date(2031, 2, 26))

    # ------------------------------------------------------------------
    # lookup() guard rails
    # ------------------------------------------------------------------
    def test_lookup_blank_callsign_raises(self):
        with self.assertRaises(UserError):
            self.Lookup.lookup("  ")

    def test_lookup_invalid_status_raises(self):
        with patch.object(self.LookupCls, "_fetch", _fake_fetch({"status": "INVALID"})):
            with self.assertRaises(UserError):
                self.Lookup.lookup("ZZ9ZZZ")

    def test_lookup_disabled_raises_without_fetching(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "club_amateur_radio.uls_lookup_enabled", "False")

        def _boom(self, callsign):
            raise AssertionError("_fetch must not be called when disabled")

        with patch.object(self.LookupCls, "_fetch", _boom):
            with self.assertRaises(UserError):
                self.Lookup.lookup("W1AW")

    def test_fetch_network_error_becomes_usererror(self):
        with patch.object(
            requests, "get", side_effect=requests.ConnectionError("no route")
        ):
            with self.assertRaises(UserError):
                self.Lookup.lookup("W1AW")

    # ------------------------------------------------------------------
    # partner button
    # ------------------------------------------------------------------
    def test_action_lookup_fills_blank_contact_and_licence(self):
        # An empty string, not False: res.partner's _check_name constraint
        # forbids a NULL name on a contact, but a blank one is allowed and is
        # what "name not filled in yet" looks like in practice.
        partner = self.env["res.partner"].create({"name": "", "callsign": "k1abc"})
        with patch.object(self.LookupCls, "_fetch", _fake_fetch(PERSON_PAYLOAD)):
            partner.action_lookup_callsign()
        self.assertEqual(partner.callsign, "K1ABC")
        self.assertEqual(partner.ham_license_class, "extra")
        self.assertEqual(partner.ham_license_expiry_date, date(2029, 3, 15))
        self.assertEqual(partner.ham_frn, "0009998887")
        self.assertEqual(partner.name, "Jane Q Doe")
        self.assertEqual(partner.street, "42 OAK LN")
        self.assertEqual(partner.state_id.code, "MA")
        self.assertEqual(partner.country_id, self.env.ref("base.us"))
        self.assertTrue(partner.ham_license_last_checked)

    def test_action_lookup_keeps_existing_name(self):
        partner = self.env["res.partner"].create(
            {"name": "Jay Doe (as we know him)", "callsign": "K1ABC"})
        with patch.object(self.LookupCls, "_fetch", _fake_fetch(PERSON_PAYLOAD)):
            partner.action_lookup_callsign()
        self.assertEqual(partner.name, "Jay Doe (as we know him)")
        self.assertEqual(partner.ham_license_class, "extra")

    def test_callsign_is_stored_uppercased(self):
        partner = self.env["res.partner"].create({"name": "X", "callsign": " w1aw "})
        self.assertEqual(partner.callsign, "W1AW")
        partner.write({"callsign": "na2aa"})
        self.assertEqual(partner.callsign, "NA2AA")

    def test_gmrs_callsign_is_stored_uppercased(self):
        partner = self.env["res.partner"].create(
            {"name": "X", "gmrs_callsign": " wqyv533 "})
        self.assertEqual(partner.gmrs_callsign, "WQYV533")
        partner.write({"gmrs_callsign": "wxyz123"})
        self.assertEqual(partner.gmrs_callsign, "WXYZ123")

    # ------------------------------------------------------------------
    # expiring-soon compute + cron activity
    # ------------------------------------------------------------------
    def test_expiring_soon_compute(self):
        partner = self.env["res.partner"].create({"name": "Y"})
        partner.ham_license_expiry_date = date.today() + timedelta(days=10)
        self.assertTrue(partner.ham_license_expiring_soon)
        partner.ham_license_expiry_date = date.today() + timedelta(days=400)
        self.assertFalse(partner.ham_license_expiring_soon)
        partner.ham_license_expiry_date = date.today() - timedelta(days=5)
        self.assertTrue(partner.ham_license_expiring_soon, "already-expired counts too")

    def test_cron_refreshes_and_raises_one_expiry_activity(self):
        partner = self.env["res.partner"].create({"name": "Z", "callsign": "K1ABC"})
        soon = dict(PERSON_PAYLOAD)
        soon["otherInfo"] = dict(
            PERSON_PAYLOAD["otherInfo"],
            expiryDate=(date.today() + timedelta(days=20)).strftime("%m/%d/%Y"),
        )
        with patch.object(self.LookupCls, "_fetch", _fake_fetch(soon)), \
                patch("odoo.addons.club_amateur_radio.models.res_partner.time.sleep"):
            self.env["res.partner"]._cron_refresh_ham_licenses()
            self.env["res.partner"]._cron_refresh_ham_licenses()
        partner.invalidate_recordset()
        self.assertEqual(partner.ham_license_class, "extra")
        self.assertTrue(partner.ham_license_expiring_soon)
        todos = partner.activity_ids.filtered(
            lambda a: (a.summary or "").startswith("Amateur radio licence expires"))
        self.assertEqual(len(todos), 1, "one To-Do, and not duplicated on a re-run")

    def test_cron_skips_when_disabled(self):
        self.env["res.partner"].create({"name": "Q", "callsign": "K1ABC"})
        self.env["ir.config_parameter"].sudo().set_param(
            "club_amateur_radio.uls_lookup_enabled", "False")

        def _boom(self, callsign):
            raise AssertionError("lookup must not run when disabled")

        with patch.object(self.LookupCls, "_fetch", _boom):
            self.env["res.partner"]._cron_refresh_ham_licenses()
