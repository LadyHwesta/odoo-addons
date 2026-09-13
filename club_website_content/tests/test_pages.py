# -*- coding: utf-8 -*-
import os

from odoo.tests.common import HttpCase, tagged
from odoo.modules.module import get_module_path

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
        # Deliberately NOT website.main_menu - that's a shared record that
        # isn't any actual website's own root, so checking its child_id
        # gives false confidence (see hooks.py's create_nav_menu
        # docstring - this is exactly the check that missed the original
        # bug). The real nav tree for a site is walked from that website's
        # own menu_id, so that's what has to be checked here.
        top_level_names = {"Our Club", "Repeaters", "Events", "Resources", "Donate"}
        website = self.env.ref("website.default_website")
        children = website.menu_id.child_id.filtered(lambda m: m.name in top_level_names)
        self.assertEqual(len(children), 5, "expected all 5 top-level section menus "
                          "under the website's own root menu")

        our_club = children.filtered(lambda m: m.name == "Our Club")
        self.assertEqual(len(our_club.child_id), 5, "Our Club should have 5 dropdown items")

        resources = children.filtered(lambda m: m.name == "Resources")
        self.assertEqual(len(resources.child_id), 10,
                          "Resources should have 10 dropdown items (incl. 6 FRS/GMRS subpages)")

    def test_menu_items_actually_render_in_the_nav(self):
        # Ground truth: render a real page and check the dropdown links
        # are actually in the HTML, rather than only checking the ORM
        # structure - that's what would have caught the original bug.
        resp = self.url_open("/our-club")
        self.assertEqual(resp.status_code, 200)
        html = resp.content
        for url in ("/our-club/meetings", "/repeaters/dmr", "/events/field-day",
                    "/resources/frs-gmrs", "/donate"):
            with self.subTest(url=url):
                self.assertIn(url.encode(), html,
                               f"{url} did not appear as a nav link in the rendered page")

    def test_homepage_serves_our_club_content(self):
        website = self.env.ref("website.default_website")
        self.assertEqual(website.homepage_url, "/our-club",
                          "the site's \"/\" should serve the ported /our-club page, "
                          "not Odoo's stock demo homepage")
        resp = self.url_open("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"About SCRA", resp.content,
                       "\"/\" did not render the /our-club page's content")

    def test_every_bundled_image_is_referenced_and_loads(self):
        # Every file actually shipped under static/src/img should be used
        # by at least one page (an unused download left behind by mistake
        # is easy to miss otherwise), and every image actually referenced
        # from a page should be a real, loadable static file - catches a
        # typo'd filename in either direction.
        img_dir = os.path.join(get_module_path("club_website_content"), "static", "src", "img")
        bundled_files = {f for f in os.listdir(img_dir) if not f.startswith(".")}
        self.assertTrue(bundled_files, "expected at least one bundled image")

        referenced = set()
        for url in PAGE_URLS:
            resp = self.url_open(url)
            html = resp.content.decode()
            for fname in bundled_files:
                if f"/club_website_content/static/src/img/{fname}" in html:
                    referenced.add(fname)

        unused = bundled_files - referenced
        self.assertFalse(unused, f"bundled images never referenced by any page: {unused}")

        for fname in bundled_files:
            with self.subTest(image=fname):
                resp = self.url_open(f"/club_website_content/static/src/img/{fname}")
                self.assertEqual(resp.status_code, 200, f"{fname} did not load")
