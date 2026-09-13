# -*- coding: utf-8 -*-
from odoo.tests.common import HttpCase, tagged

# Every page this module creates - kept as one flat list so a missing or
# broken page shows up immediately rather than needing separate lookups.
PAGE_URLS = [
    "/our-club",
    "/our-club/meetings",
    "/our-club/club-officials",
    "/our-club/contact-us",
    "/our-club/short-skip",
    "/our-club/club-insurance",
    "/repeaters",
    "/repeaters/dmr",
    "/repeaters/dmr/is-easy",
    "/repeaters/dmr/code-plugs",
    "/repeaters/yaesu-fusion",
    "/repeaters/irlp",
    "/repeaters/policy",
    "/events",
    "/events/classes",
    "/events/ve-testing",
    "/events/public-service",
    "/events/field-day",
    "/events/winter-field-day",
    "/resources",
    "/resources/net-script",
    "/resources/emergency-services",
    "/resources/frs-gmrs",
    "/resources/frs-gmrs/faqs",
    "/resources/frs-gmrs/radios",
    "/resources/frs-gmrs/why",
    "/resources/frs-gmrs/emergency-ops",
    "/resources/frs-gmrs/activity-in-sonoma-county",
    "/resources/useful-links",
    "/resources/smartphone-apps",
    "/donate",
]


@tagged("post_install", "-at_install")
class TestClubWebsiteContentPages(HttpCase):

    def test_every_page_exists_and_is_published(self):
        pages = self.env["website.page"].search([("url", "in", PAGE_URLS)])
        found_urls = set(pages.mapped("url"))
        missing = set(PAGE_URLS) - found_urls
        self.assertFalse(missing, f"website.page records missing for: {missing}")
        self.assertTrue(all(pages.mapped("is_published")),
                         "every ported page should be published")

    def test_every_page_loads_200(self):
        for url in PAGE_URLS:
            with self.subTest(url=url):
                resp = self.url_open(url)
                self.assertEqual(resp.status_code, 200, f"{url} did not return 200")

    def test_menu_structure(self):
        top_level_names = {"Our Club", "Repeaters", "Events", "Resources", "Donate"}
        main_menu = self.env.ref("website.main_menu")
        children = main_menu.child_id.filtered(lambda m: m.name in top_level_names)
        self.assertEqual(len(children), 5, "expected all 5 top-level section menus")

        our_club = children.filtered(lambda m: m.name == "Our Club")
        self.assertEqual(len(our_club.child_id), 5, "Our Club should have 5 dropdown items")

        resources = children.filtered(lambda m: m.name == "Resources")
        self.assertEqual(len(resources.child_id), 10,
                          "Resources should have 10 dropdown items (incl. 6 FRS/GMRS subpages)")
