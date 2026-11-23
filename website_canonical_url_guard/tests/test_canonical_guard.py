# -*- coding: utf-8 -*-
from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestCanonicalGuard(HttpCase):

    def test_bot_probes_get_a_plain_not_found_page(self):
        for path in ('//wp-login.php', '/a/%2e%2e/etc/passwd', '/foo/%2e/bar'):
            with self.subTest(path=path), self.assertNoLogs('odoo.addons.http_routing', 'ERROR'):
                response = self.url_open(path, allow_redirects=False)
                self.assertIn(response.status_code, (404, 301, 302, 308), path)

    def test_normal_pages_keep_their_canonical_link(self):
        page = self.url_open('/contactus').text
        self.assertIn('rel="canonical"', page)
        self.assertIn('/contactus', page.split('rel="canonical"')[1][:200])
