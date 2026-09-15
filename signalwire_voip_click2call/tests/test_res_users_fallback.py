# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestResUsersFallback(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env['res.users'].create({
            'name': 'Jane Agent', 'login': 'jane.agent@example.com',
        })

    def test_use_profile_phone_creates_a_saved_number(self):
        self.user.partner_id.phone = '+15551234567'

        number = self.user.action_use_profile_phone_as_forward()

        self.assertEqual(number.phone_number, '+15551234567')
        self.assertEqual(number.name, 'Profile Phone')
        self.assertIn(number, self.user.signalwire_forwarding_number_ids)

    def test_use_profile_phone_with_none_set_raises(self):
        self.user.partner_id.phone = False
        with self.assertRaises(UserError):
            self.user.action_use_profile_phone_as_forward()

    def test_use_profile_phone_twice_does_not_duplicate(self):
        self.user.partner_id.phone = '+15551234567'
        first = self.user.action_use_profile_phone_as_forward()

        second = self.user.action_use_profile_phone_as_forward()

        self.assertEqual(first, second)
        self.assertEqual(len(self.user.signalwire_forwarding_number_ids), 1)

    def test_match_partner_finds_by_digits_only(self):
        partner = self.env['res.partner'].create({
            'name': 'Jane Customer', 'phone': '+1 (555) 610-2107',
        })
        found = self.user._signalwire_match_partner('+15556102107')
        self.assertEqual(found, partner)

    def test_match_partner_no_match_returns_empty(self):
        found = self.user._signalwire_match_partner('+19995550000')
        self.assertFalse(found)
