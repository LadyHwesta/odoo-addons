# -*- coding: utf-8 -*-
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSignalWireIvrMenu(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env['res.users'].create({
            'name': 'Jane Agent', 'login': 'jane.agent@example.com'})
        cls.menu = cls.env['signalwire.ivr.menu'].create({
            'name': 'Main Menu', 'greeting_text': 'Press 1 for sales.',
        })

    def test_option_digit_must_be_unique_per_menu(self):
        self.env['signalwire.ivr.menu.option'].create({
            'menu_id': self.menu.id, 'digit': '1', 'action_type': 'user',
            'target_user_id': self.user.id,
        })
        with self.assertRaises(Exception):
            self.env['signalwire.ivr.menu.option'].create({
                'menu_id': self.menu.id, 'digit': '1', 'action_type': 'hangup',
            })

    def test_option_follows_its_menu_own_company(self):
        option = self.env['signalwire.ivr.menu.option'].create({
            'menu_id': self.menu.id, 'digit': '1', 'action_type': 'user',
            'target_user_id': self.user.id,
        })
        self.assertEqual(option.company_id, self.menu.company_id)

    def test_target_user_from_a_different_company_is_rejected(self):
        other_company = self.env['res.company'].create({'name': 'Other Co'})
        outside_user = self.env['res.users'].create({
            'name': 'Outsider', 'login': 'outsider@example.com',
            'company_ids': [(6, 0, [other_company.id])],
            'company_id': other_company.id,
        })
        with self.assertRaises(UserError):
            self.env['signalwire.ivr.menu.option'].create({
                'menu_id': self.menu.id, 'digit': '2', 'action_type': 'user',
                'target_user_id': outside_user.id,
            })

    def test_target_submenu_from_a_different_company_is_rejected(self):
        other_company = self.env['res.company'].create({'name': 'Other Co'})
        other_menu = self.env['signalwire.ivr.menu'].create({
            'name': 'Other Menu', 'greeting_text': 'Hi.',
            'company_id': other_company.id,
        })
        with self.assertRaises(UserError):
            self.env['signalwire.ivr.menu.option'].create({
                'menu_id': self.menu.id, 'digit': '3', 'action_type': 'submenu',
                'target_submenu_id': other_menu.id,
            })


@tagged('post_install', '-at_install')
class TestSignalWireCallGroupCompanyScoping(TransactionCase):

    def test_member_from_a_different_company_is_rejected(self):
        other_company = self.env['res.company'].create({'name': 'Other Co'})
        outside_user = self.env['res.users'].create({
            'name': 'Outsider', 'login': 'outsider2@example.com',
            'company_ids': [(6, 0, [other_company.id])],
            'company_id': other_company.id,
        })
        with self.assertRaises(ValidationError):
            self.env['signalwire.call.group'].create({
                'name': 'Sales', 'member_ids': [(6, 0, [outside_user.id])],
            })
