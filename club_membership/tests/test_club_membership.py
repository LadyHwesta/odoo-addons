# -*- coding: utf-8 -*-
import re
from datetime import date, datetime, timedelta

from odoo.tests.common import HttpCase, TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestClubMembership(TransactionCase):
    def test_annual_dues_product(self):
        product = self.env.ref("club_membership.product_annual_dues")
        self.assertTrue(product.membership)
        self.assertTrue(product.membership_prorate)
        self.assertEqual(product.membership_date_from.year, date.today().year)
        self.assertEqual(product.membership_date_to,
                         date(date.today().year, 12, 31))

    def test_club_menu_installed(self):
        self.assertTrue(self.env.ref("club_membership.menu_club_root"))
        self.assertTrue(self.env.ref("club_membership.menu_club_equipment_loans"))

    def test_year_roll_cron(self):
        product = self.env.ref("club_membership.product_annual_dues")
        product.write({
            "membership_date_from": date(date.today().year - 1, 1, 1),
            "membership_date_to": date(date.today().year - 1, 12, 31),
        })
        # a plain (non-prorate) membership product must be left alone
        plain = self.env["product.product"].create({
            "name": "Life membership",
            "membership": True,
            "membership_date_from": date(date.today().year - 1, 1, 1),
            "membership_date_to": date(date.today().year - 1, 12, 31),
        })
        rolled = self.env["product.template"]._cron_roll_membership_year()
        self.assertEqual(rolled, 1)
        self.assertEqual(product.membership_date_from, date(date.today().year, 1, 1))
        self.assertEqual(product.membership_date_to, date(date.today().year, 12, 31))
        self.assertEqual(plain.membership_date_to, date(date.today().year - 1, 12, 31))


@tagged("post_install", "-at_install")
class TestClubPortal(HttpCase):
    def test_my_club_page(self):
        user = self.env["res.users"].create({
            "name": "Portal Ham", "login": "ham_portal", "password": "ham_portal",
            "group_ids": [(6, 0, [self.env.ref("base.group_portal").id])],
        })
        partner = user.partner_id
        partner.write({
            "callsign": "k9xyz",
            "ham_license_class": "general",
            "ham_license_expiry_date": date.today() + timedelta(days=20),
            "free_member": True,
        })

        equipment = self.env["maintenance.equipment"].create({
            "name": "Kenwood TS-590", "is_loanable": True})
        self.env["club.equipment.loan"].create({
            "equipment_id": equipment.id, "borrower_id": partner.id,
            "borrower_accepted": True,
        }).action_check_out()

        event = self.env["event.event"].create({
            "name": "Winter Field Day",
            "date_begin": datetime.now() + timedelta(days=10),
            "date_end": datetime.now() + timedelta(days=11),
        })
        role = self.env["event.volunteer.role"].create({
            "event_id": event.id, "name": "Logger", "slot_count": 3})
        self.env["event.volunteer.assignment"].create({
            "role_id": role.id, "partner_id": partner.id, "state": "confirmed"})

        self.authenticate("ham_portal", "ham_portal")
        resp = self.url_open("/my/club")
        self.assertEqual(resp.status_code, 200)
        body = resp.text
        self.assertIn("K9XYZ", body)
        self.assertIn("Kenwood TS-590", body)
        self.assertIn("Winter Field Day", body)
        self.assertIn("Renew soon", body)  # licence within the warn window

        home = self.url_open("/my")
        self.assertEqual(home.status_code, 200)
        self.assertIn("My Club", home.text)


@tagged("post_install", "-at_install")
class TestBackendAssets(HttpCase):
    """Guard against a repo-layout mistake breaking the backend SCSS bundle.
    A top-level dir named `vendor` on the addons path shadows Bootstrap's
    own `scss/vendor/` (Odoo's SCSS importer resolves `file_path("vendor")`
    first), which fails `@import "vendor/rfs"` and poisons web.assets_web -
    but an SCSS error is swallowed into css_errors and the page still
    returns 200, so it only shows in the browser console."""

    def test_web_assets_web_compiles_without_scss_error(self):
        self.authenticate("admin", "admin")
        page = self.url_open("/odoo")
        self.assertEqual(page.status_code, 200)
        match = re.search(
            r'href="([^"]*web\.assets_web[^"]*\.css[^"]*)"', page.text)
        self.assertTrue(match, "web.assets_web stylesheet link not on /odoo")
        css = self.url_open(match.group(1))
        self.assertEqual(css.status_code, 200)
        self.assertNotIn("A css error occured", css.text)
        self.assertNotIn("css_error_message", css.text)
