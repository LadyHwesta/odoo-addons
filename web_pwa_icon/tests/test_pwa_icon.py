# -*- coding: utf-8 -*-
from odoo.tests.common import HttpCase, TransactionCase, tagged

# A 1x1 transparent PNG - resizing doesn't care about real content.
PNG_1PX = (
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8'
    'z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
)


@tagged('post_install', '-at_install')
class TestPwaSettingsVisibility(TransactionCase):

    def test_pwa_block_visible_without_developer_mode(self):
        """The name+icon block shows up for a plain admin, not just one
        with developer mode's base.group_no_one enabled."""
        admin = self.env.ref('base.user_admin')
        self.assertNotIn(
            self.env.ref('base.group_no_one'), admin.group_ids,
            "test assumption broken: admin already has group_no_one",
        )
        arch = self.env['res.config.settings'].with_user(admin).get_view()['arch']
        self.assertIn('id="pwa_settings"', arch)
        self.assertIn('name="web_app_name"', arch)
        self.assertIn('name="pwa_icon"', arch)


@tagged('post_install', '-at_install')
class TestPwaIcon(HttpCase):

    def setUp(self):
        super().setUp()
        # Every test starts from "no custom icon configured" regardless of
        # what a previous test in this class left behind.
        self.env.company.pwa_icon = False

    def test_manifest_default_icons_when_unset(self):
        """With no custom icon, the manifest is untouched - same paths
        core Odoo has always served."""
        resp = self.url_open('/web/manifest.webmanifest')
        self.assertEqual(resp.status_code, 200)
        icons = resp.json()['icons']
        self.assertEqual(
            {icon['src'] for icon in icons},
            {'/web/static/img/odoo-icon-192x192.png',
             '/web/static/img/odoo-icon-512x512.png'},
        )

    def test_manifest_points_at_custom_route_when_set(self):
        self.env.company.pwa_icon = PNG_1PX
        resp = self.url_open('/web/manifest.webmanifest')
        self.assertEqual(resp.status_code, 200)
        icons = resp.json()['icons']
        self.assertEqual(
            {icon['src'] for icon in icons},
            {'/web/pwa_icon/192x192', '/web/pwa_icon/512x512'},
        )

    def test_pwa_icon_route_falls_back_without_custom_icon(self):
        # request.redirect() defaults to a 303 (See Other), not a 302.
        resp = self.url_open('/web/pwa_icon/192x192', allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(resp.headers['Location'], '/web/static/img/odoo-icon-192x192.png')

        # The apple-touch-icon size isn't one of the manifest's own sizes -
        # falls back to the iOS-specific default, not the 192x192 one.
        resp = self.url_open('/web/pwa_icon/180x180', allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(resp.headers['Location'], '/web/static/img/odoo-icon-ios.png')

    def test_pwa_icon_route_serves_custom_image(self):
        self.env.company.pwa_icon = PNG_1PX
        resp = self.url_open('/web/pwa_icon/192x192')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers['Content-Type'], 'image/png')

    def test_apple_touch_icon_link_uses_custom_route(self):
        self.authenticate('admin', 'admin')
        page = self.url_open('/odoo')
        self.assertIn(
            '<link rel="apple-touch-icon" href="/web/pwa_icon/180x180"/>',
            page.text,
        )
