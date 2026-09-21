# -*- coding: utf-8 -*-
from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestSupportCallPortalController(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Portal Customer'})
        cls.portal_user = cls.env['res.users'].create({
            'name': 'Portal Customer', 'login': 'portal.customer@example.com',
            'partner_id': cls.partner.id,
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })
        cls.portal_user.sudo().write({'password': 'portal_test_pw_123'})

    def test_support_call_page_404s_without_a_tier(self):
        self.authenticate('portal.customer@example.com', 'portal_test_pw_123')

        response = self.url_open('/my/support/call')

        self.assertEqual(response.status_code, 404)

    def test_support_call_page_loads_with_a_tier(self):
        self.partner.signalwire_portal_support_tier = 'callback'
        self.authenticate('portal.customer@example.com', 'portal_test_pw_123')

        response = self.url_open('/my/support/call')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Request a Callback', response.content)

    def test_submit_without_a_tier_creates_nothing(self):
        self.authenticate('portal.customer@example.com', 'portal_test_pw_123')
        before = self.env['signalwire.callback_request'].search_count([])

        self.url_open('/my/support/call/submit', data={
            'phone_number': '+15551234567',
            'csrf_token': self._get_csrf_token(),
        })

        self.assertEqual(self.env['signalwire.callback_request'].search_count([]), before)

    def test_submit_with_a_tier_creates_a_request(self):
        self.partner.signalwire_portal_support_tier = 'callback'
        self.authenticate('portal.customer@example.com', 'portal_test_pw_123')

        self.url_open('/my/support/call/submit', data={
            'phone_number': '+15551234567', 'note': 'Please call after 3pm',
            'csrf_token': self._get_csrf_token(),
        })

        request_ = self.env['signalwire.callback_request'].search(
            [('partner_id', '=', self.partner.id)])
        self.assertEqual(len(request_), 1)
        self.assertEqual(request_.phone_number, '+15551234567')
        self.assertEqual(request_.note, 'Please call after 3pm')

    def _get_csrf_token(self):
        response = self.url_open('/my/support/call')
        # A real page render always embeds a fresh CSRF token in the
        # submit form - extract it rather than computing one by hand,
        # so this test exercises the real token the browser would use.
        import re
        match = re.search(rb'name="csrf_token" value="([^"]+)"', response.content)
        return match.group(1).decode() if match else ''
