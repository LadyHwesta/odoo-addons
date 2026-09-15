# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestResPartnerNamecheapFields(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.us = cls.env.ref('base.us')
        cls.partner = cls.env['res.partner'].create({
            'name': 'Jane Customer',
            'street': '123 Main St',
            'city': 'Springfield',
            'zip': '55555',
            'country_id': cls.us.id,
            'phone': '+1 555-610-2107',
            'email': 'jane@example.com',
        })

    def test_registrant_fields_maps_the_address(self):
        fields_ = self.partner._namecheap_registrant_fields()
        self.assertEqual(fields_['FirstName'], 'Jane')
        self.assertEqual(fields_['LastName'], 'Customer')
        self.assertEqual(fields_['Address1'], '123 Main St')
        self.assertEqual(fields_['City'], 'Springfield')
        self.assertEqual(fields_['PostalCode'], '55555')
        self.assertEqual(fields_['Country'], 'US')
        self.assertEqual(fields_['EmailAddress'], 'jane@example.com')

    def test_registrant_fields_single_word_name_used_for_both(self):
        self.partner.name = 'Cher'
        fields_ = self.partner._namecheap_registrant_fields()
        self.assertEqual(fields_['FirstName'], 'Cher')
        self.assertEqual(fields_['LastName'], 'Cher')

    def test_registrant_fields_raises_on_missing_address(self):
        partner = self.env['res.partner'].create({'name': 'Incomplete Guy'})
        with self.assertRaises(UserError):
            partner._namecheap_registrant_fields()

    def test_format_phone_adds_country_code_when_missing(self):
        self.partner.phone = '5556102107'
        self.assertEqual(self.partner._namecheap_format_phone(), '+1.5556102107')

    def test_format_phone_splits_an_already_prefixed_number(self):
        self.partner.phone = '+1 555-610-2107'
        self.assertEqual(self.partner._namecheap_format_phone(), '+1.5556102107')

    def test_format_phone_with_no_country_still_adds_a_plus(self):
        self.partner.country_id = False
        self.partner.phone = '5556102107'
        self.assertEqual(self.partner._namecheap_format_phone(), '+5556102107')
