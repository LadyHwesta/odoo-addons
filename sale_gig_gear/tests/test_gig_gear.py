# -*- coding: utf-8 -*-
from datetime import date

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestGigGear(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Gear = cls.env['gig.gear.item']
        cls.speaker = Gear.create({'name': 'Powered speaker 12"', 'category': 'sound', 'quantity': 4})
        cls.controller = Gear.create({'name': 'DJ controller', 'category': 'dj', 'quantity': 1})
        cls.uplight = Gear.create({'name': 'Uplight', 'category': 'lights', 'quantity': 8})
        cls.package = cls.env['product.product'].create({
            'name': 'Wedding package', 'type': 'service', 'list_price': 1200,
            'gig_gear_default_ids': [(0, 0, {'gear_id': cls.speaker.id, 'quantity': 2}),
                                     (0, 0, {'gear_id': cls.controller.id, 'quantity': 1})]})
        cls.dance_floor = cls.env['product.product'].create({
            'name': 'Dance floor sound', 'type': 'service', 'list_price': 200,
            'gig_gear_default_ids': [(0, 0, {'gear_id': cls.speaker.id, 'quantity': 2})]})
        cls.client = cls.env['res.partner'].create({'name': 'Sam & Alex'})

    def _order(self, *products, gig=True):
        return self.env['sale.order'].create({
            'partner_id': self.client.id, 'gig_date': date(2027, 6, 12) if gig else False,
            'gig_start_hour': 17.0, 'gig_end_hour': 23.0, 'venue_name': 'Barn',
            'order_line': [(0, 0, {'product_id': p.id}) for p in products]})

    def _gear(self, order):
        return {line.gear_id.name: line.quantity for line in order.gig_gear_line_ids}

    def test_booking_a_gig_fills_its_checklist(self):
        order = self._order(self.package, self.dance_floor)
        order.with_context(gig_conflict_ok=True).action_confirm()
        self.assertEqual(self._gear(order), {'Powered speaker 12"': 4, 'DJ controller': 1})
        self.assertEqual(order.gig_gear_progress, '0 of 2 packed')
        order.gig_gear_line_ids[0].packed = True
        self.assertEqual(order.gig_gear_progress, '1 of 2 packed')

    def test_a_plain_order_gets_no_checklist(self):
        order = self._order(self.package, gig=False)
        order.action_confirm()
        self.assertFalse(order.gig_gear_line_ids)

    def test_adding_again_keeps_what_you_added(self):
        order = self._order(self.package)
        order.action_gig_load_gear()
        order.gig_gear_line_ids.filtered(lambda l: l.gear_id == self.speaker).quantity = 3
        self.env['gig.gear.line'].create({'order_id': order.id, 'gear_id': self.uplight.id, 'quantity': 6})
        order.write({'order_line': [(0, 0, {'product_id': self.dance_floor.id})]})
        order.action_gig_load_gear()
        self.assertEqual(self._gear(order), {'Powered speaker 12"': 4, 'DJ controller': 1, 'Uplight': 6})

    def test_needing_more_than_you_own_is_flagged(self):
        order = self._order(self.package, self.dance_floor, self.dance_floor)
        order.action_gig_load_gear()
        self.assertEqual(self._gear(order)['Powered speaker 12"'], 6)
        self.assertTrue(order.gig_gear_short)

    def test_load_in_sheet_lists_the_gear(self):
        order = self._order(self.package)
        order.action_gig_load_gear()
        order.gig_gear_line_ids.filtered(lambda l: l.gear_id == self.controller).packed = True
        html = self.env['ir.actions.report']._render_qweb_html(
            'sale_gig_booking.report_gig_load_in', order.ids)[0].decode()
        for text in ('Speakers &amp; sound', 'Powered speaker 12', 'DJ controller', '☑', '☐', '1 of 2 packed'):
            self.assertIn(text, html)

    def test_sheet_groups_by_category_and_carries_notes(self):
        self.speaker.note = 'Black cases'
        order = self._order(self.dance_floor, self.package)  # speakers first, controller second
        order.action_gig_load_gear()
        self.assertEqual([l.category for l in order._gig_gear_sheet_lines()], ['dj', 'sound'])
        self.assertEqual(order.gig_gear_line_ids.filtered(lambda l: l.gear_id == self.speaker).note,
                         'Black cases')
