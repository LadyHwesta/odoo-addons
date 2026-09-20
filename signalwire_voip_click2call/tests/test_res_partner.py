# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestResPartnerClick2Call(TransactionCase):

    def test_format_partner_adds_the_country_code(self):
        partner = self.env['res.partner'].create({
            'name': 'Example Contact',
            'country_id': self.env.ref('base.us').id,
            'phone': '(707) 555-0123',
        })
        self.assertEqual(partner.format_partner()['phone'], '+17075550123')

    def test_format_partner_leaves_an_already_qualified_number_alone(self):
        partner = self.env['res.partner'].create({
            'name': 'Example Contact',
            'country_id': self.env.ref('base.us').id,
            'phone': '+17075550123',
        })
        self.assertEqual(partner.format_partner()['phone'], '+17075550123')

    def test_format_partner_falls_back_to_the_raw_number_when_unformattable(self):
        partner = self.env['res.partner'].create({
            'name': 'Example Contact', 'country_id': False, 'phone': 'not-a-number',
        })
        self.assertEqual(partner.format_partner()['phone'], 'not-a-number')

    def test_format_partner_with_no_phone_stays_falsy(self):
        partner = self.env['res.partner'].create({'name': 'Example Contact', 'phone': False})
        self.assertFalse(partner.format_partner()['phone'])
