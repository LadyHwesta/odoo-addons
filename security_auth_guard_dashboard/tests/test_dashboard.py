# -*- coding: utf-8 -*-
import json

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestThreatDashboard(TransactionCase):
    def setUp(self):
        super().setUp()
        self.dashboard = self.env.ref(
            "security_auth_guard_dashboard.dashboard_threats")
        self.data = json.loads(self.dashboard.spreadsheet_data)

    def _sources(self):
        yield from self.data["pivots"].values()
        yield from self.data["lists"].values()

    def test_every_model_and_field_it_uses_exists(self):
        for source in self._sources():
            model = self.env[source["model"]]
            names = list(source.get("columns", []))
            if "measures" in source:
                names += [row["fieldName"] for row in source["rows"]]
            for name in names:
                with self.subTest(model=source["model"], field=name):
                    self.assertIn(name, model._fields)

    def test_every_menu_link_exists(self):
        cells = self.data["sheets"][0]["cells"]
        links = [c for c in cells.values() if "odoo://ir_menu_xml_id/" in str(c)]
        self.assertTrue(links)
        for link in links:
            xmlid = link.split("odoo://ir_menu_xml_id/")[1].rstrip(")")
            self.assertTrue(self.env.ref(xmlid, raise_if_not_found=False), xmlid)

    def test_only_security_officers_can_open_it(self):
        ordinary = new_test_user(
            self.env, login="dash_ordinary", groups="base.group_user")
        officer = new_test_user(
            self.env, login="dash_officer",
            groups="base.group_user,security_auth_guard.group_security_officer")
        self.dashboard.with_user(officer).check_access("read")
        with self.assertRaises(AccessError):
            self.dashboard.with_user(ordinary).check_access("read")

    def test_serialized_dashboard_is_valid(self):
        served = json.loads(self.dashboard._get_serialized_readonly_dashboard())
        self.assertEqual(served["snapshot"]["sheets"][0]["name"], "Dashboard")
