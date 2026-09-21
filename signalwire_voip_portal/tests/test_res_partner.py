# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestResPartnerPortalTier(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group = cls.env.ref('signalwire_voip_portal.group_signalwire_portal_calling')

    def _portal_partner_with_login(self):
        partner = self.env['res.partner'].create({'name': 'Portal Customer'})
        user = self.env['res.users'].create({
            'name': 'Portal Customer', 'login': f'portal{partner.id}@example.com',
            'partner_id': partner.id,
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        return partner, user

    def test_setting_a_tier_grants_the_group(self):
        partner, user = self._portal_partner_with_login()
        self.assertNotIn(self.group, user.group_ids)

        partner.signalwire_portal_support_tier = 'callback'

        self.assertIn(self.group, user.group_ids)

    def test_clearing_the_tier_revokes_the_group(self):
        partner, user = self._portal_partner_with_login()
        partner.signalwire_portal_support_tier = 'live_call'
        self.assertIn(self.group, user.group_ids)

        partner.signalwire_portal_support_tier = 'none'

        self.assertNotIn(self.group, user.group_ids)

    def test_a_partner_with_no_login_does_not_error(self):
        partner = self.env['res.partner'].create({'name': 'No Login Contact'})
        partner.signalwire_portal_support_tier = 'callback'  # should not raise

    def test_tier_set_before_the_portal_login_exists_still_syncs(self):
        # The common real-world order: a partner exists and its tier
        # gets set first, the portal invite/login comes later - the
        # sync needs to catch up from the res.users side too, not
        # just fire once from res.partner's own create()/write().
        partner = self.env['res.partner'].create({
            'name': 'Portal Customer 2', 'signalwire_portal_support_tier': 'callback'})

        user = self.env['res.users'].create({
            'name': 'Portal Customer 2', 'login': f'portal2{partner.id}@example.com',
            'partner_id': partner.id,
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])],
        })

        self.assertIn(self.group, user.group_ids)
