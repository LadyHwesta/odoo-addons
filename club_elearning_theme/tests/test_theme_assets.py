# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestThemeAssets(TransactionCase):
    def test_frontend_bundle_compiles_with_course_styling(self):
        bundle = self.env["ir.qweb"]._get_asset_bundle("web.assets_frontend")
        attachments = bundle.css()
        self.assertFalse(bundle.css_errors, bundle.css_errors)
        content = b"".join(a.raw for a in attachments)
        self.assertIn(b"oe-course-content", content)
        self.assertIn(b"oe-callout", content)
