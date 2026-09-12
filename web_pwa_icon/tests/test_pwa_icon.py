# -*- coding: utf-8 -*-
import base64

from odoo.tests.common import HttpCase, TransactionCase, tagged


def _make_512_png():
    # web_pwa_customize rejects anything smaller than 512x512, so build a
    # real one rather than relying on the 1x1 placeholder above.
    from PIL import Image
    import io
    buf = io.BytesIO()
    Image.new('RGBA', (512, 512), (255, 0, 0, 255)).save(buf, format='PNG')
    return base64.b64encode(buf.getvalue())


@tagged('post_install', '-at_install')
class TestPwaSettingsVisibility(TransactionCase):

    def test_pwa_block_visible_without_developer_mode(self):
        """The name/short-name/colors/icon block shows up for a plain
        admin, not just one with developer mode's base.group_no_one."""
        admin = self.env.ref('base.user_admin')
        self.assertNotIn(
            self.env.ref('base.group_no_one'), admin.group_ids,
            "test assumption broken: admin already has group_no_one",
        )
        arch = self.env['res.config.settings'].with_user(admin).get_view()['arch']
        self.assertIn('id="pwa_settings"', arch)
        self.assertIn('name="web_app_name"', arch)
        self.assertIn('name="pwa_short_name"', arch)
        self.assertIn('name="pwa_icon"', arch)


@tagged('post_install', '-at_install')
class TestAppleTouchIcon(HttpCase):

    def setUp(self):
        super().setUp()
        # Every test starts from "no custom icon configured" regardless of
        # what a previous test in this class left behind.
        self.env['res.config.settings'].create({'pwa_icon': False}).execute()

    def test_falls_back_to_odoo_icon_without_custom_icon(self):
        resp = self.url_open('/web/pwa_icon/apple-touch-icon.png', allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(resp.headers['Location'], '/web/static/img/odoo-icon-ios.png')

    def test_redirects_to_web_pwa_customize_icon_when_set(self):
        self.env['res.config.settings'].create({'pwa_icon': _make_512_png()}).execute()
        resp = self.url_open('/web/pwa_icon/apple-touch-icon.png', allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(resp.headers['Location'], '/web_pwa_customize/icon192x192.png')

    def test_apple_touch_icon_link_uses_our_route(self):
        self.authenticate('admin', 'admin')
        page = self.url_open('/odoo')
        self.assertIn(
            '<link rel="apple-touch-icon" href="/web/pwa_icon/apple-touch-icon.png"/>',
            page.text,
        )
