# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestResellerMenu(TransactionCase):
    """The Customers section shows only in a database that resells."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group = cls.env.ref('signalwire_voip.group_signalwire_reseller')
        cls.admins = cls.env.ref('base.group_system')
        cls.menu = cls.env.ref('signalwire_voip.menu_signalwire_section_customers')
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test', 'space': 'example.signalwire.com', 'project_id': 'pid', 'api_token': 'tok'})
        cls.Sub = cls.env['signalwire.subproject']
        cls.Sub.search([]).unlink()  # start from a database that resells nothing

    def _admin_sees_menu(self):
        admin = self.env.ref('base.user_admin')
        self.env.invalidate_all()
        visible = self.env['ir.ui.menu'].with_user(admin)._visible_menu_ids()
        return self.menu.id in visible

    def test_own_sub_account_keeps_it_hidden(self):
        self.Sub.create({'name': 'Ours', 'server_id': self.server.id, 'account_sid': 'own',
                         'partner_id': self.env.company.partner_id.id})
        self.assertNotIn(self.group, self.admins.implied_ids)
        self.assertFalse(self._admin_sees_menu())

    def test_customer_sub_account_shows_it_and_removing_hides_it(self):
        customer = self.env['res.partner'].create({'name': 'TFL Conference'})
        theirs = self.Sub.create({'name': 'TFL', 'server_id': self.server.id, 'account_sid': 'sub-tfl',
                                  'partner_id': customer.id})
        self.assertIn(self.group, self.admins.implied_ids)
        self.assertTrue(self._admin_sees_menu())
        theirs.unlink()
        self.assertNotIn(self.group, self.admins.implied_ids)
        self.assertFalse(self._admin_sees_menu())
