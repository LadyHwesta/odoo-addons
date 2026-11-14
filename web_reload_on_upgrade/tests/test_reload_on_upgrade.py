# -*- coding: utf-8 -*-
import re

from odoo.tests.common import HttpCase, tagged

VERSION_URL = '/web_reload_on_upgrade/version'

# Runs inside the open web client. browser.location.reload is swapped for a
# marker so the test can see whether the service would have reloaded.
SETUP_JS = """
while (!odoo.__WOWL_DEBUG__?.root.env.services.web_reload_on_upgrade) {
    await new Promise((resolve) => setTimeout(resolve, 50));
}
const { browser } = odoo.loader.modules.get("@web/core/browser/browser");
const { session } = odoo.loader.modules.get("@web/session");
const service = odoo.__WOWL_DEBUG__.root.env.services.web_reload_on_upgrade;
let reloaded = false;
const location = { reload: () => { reloaded = true; } };
for (const key of ["href", "origin", "protocol", "host", "hostname", "port",
                   "pathname", "search", "hash"]) {
    Object.defineProperty(location, key, { get: () => window.location[key] });
}
location.assign = (url) => window.location.assign(url);
location.replace = (url) => window.location.replace(url);
Object.defineProperty(browser, "location", { get: () => location, configurable: true });
"""


def in_page(code):
    """browser_js evaluates an expression, so the awaits need a function."""
    return f"(async () => {{ {SETUP_JS} {code} }})()"


@tagged('post_install', '-at_install')
class TestReloadOnUpgrade(HttpCase):

    def test_version_matches_the_web_client(self):
        """The route answers with the same fingerprint the web client is
        started with, so an unchanged server never triggers a reload."""
        self.authenticate('admin', 'admin')
        page = self.url_open('/odoo')
        self.assertEqual(page.status_code, 200)
        started_with = re.search(r'"registry_hash":\s*"([^"]+)"', page.text)
        self.assertTrue(started_with, "registry_hash not found in the web client page")

        response = self.url_open(VERSION_URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'registry_hash': started_with.group(1)})
        self.assertIn('no-store', response.headers.get('Cache-Control', ''))

    def test_version_needs_a_login(self):
        response = self.url_open(VERSION_URL, allow_redirects=False)
        self.assertNotEqual(response.status_code, 200)

    def test_same_version_does_not_reload(self):
        self.browser_js('/odoo', in_page("""
            const outdated = await service.check({ returning: true });
            if (outdated || reloaded) {
                throw new Error("reloaded although the server wasn't upgraded");
            }
            console.log("test successful");
        """), login='admin')

    def test_upgraded_server_reloads_on_return(self):
        """Coming back to the window after an upgrade reloads it."""
        self.browser_js('/odoo', in_page("""
            session.registry_hash = "from-before-the-upgrade";
            const outdated = await service.check({ returning: true });
            if (!outdated || !reloaded) {
                throw new Error("an upgraded server didn't reload the window");
            }
            console.log("test successful");
        """), login='admin')

    def test_upgraded_server_while_in_use_asks_first(self):
        """When the upgrade is noticed while the window is in use (the
        connection came back after the restart), it asks instead of
        reloading under the person's hands."""
        self.browser_js('/odoo', in_page("""
            session.registry_hash = "from-before-the-upgrade";
            const outdated = await service.check();
            if (!outdated || reloaded) {
                throw new Error("expected an offer to reload, not a reload");
            }
            await new Promise((resolve) => setTimeout(resolve, 100));
            const offer = [...document.querySelectorAll(".o_notification")]
                .find((el) => el.textContent.includes("Odoo has been updated"));
            if (!offer) {
                throw new Error("no reload offer shown");
            }
            [...offer.querySelectorAll("button")]
                .find((button) => button.textContent.trim() === "Reload").click();
            for (let i = 0; i < 40 && !reloaded; i++) {
                await new Promise((resolve) => setTimeout(resolve, 50));
            }
            if (!reloaded) {
                throw new Error("the Reload button didn't reload");
            }
            console.log("test successful");
        """), login='admin')
