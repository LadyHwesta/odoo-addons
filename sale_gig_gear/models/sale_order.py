# -*- coding: utf-8 -*-
from collections import Counter

from odoo import _, api, fields, models

from .gig_gear_item import GEAR_CATEGORIES


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    gig_gear_line_ids = fields.One2many('gig.gear.line', 'order_id', string="Gear", copy=True)
    gig_gear_progress = fields.Char(compute='_compute_gig_gear_progress', string="Packed")
    gig_gear_short = fields.Boolean(compute='_compute_gig_gear_progress')

    @api.depends('gig_gear_line_ids.packed', 'gig_gear_line_ids.quantity')
    def _compute_gig_gear_progress(self):
        for order in self:
            lines = order.gig_gear_line_ids
            order.gig_gear_progress = _("%(done)s of %(total)s packed",
                                        done=len(lines.filtered('packed')), total=len(lines)) if lines else False
            order.gig_gear_short = any(lines.mapped('short'))

    def _gig_gear_needed(self):
        """Gear the booked packages and add-ons need, added up across lines
        (two products each needing 2 speakers need 4)."""
        self.ensure_one()
        needed = Counter()
        for line in self.order_line.filtered(lambda l: not l.display_type and l.product_id):
            for default in line.product_id.product_tmpl_id.gig_gear_default_ids:
                needed[default.gear_id] += default.quantity
        return needed

    def action_gig_load_gear(self):
        """Add the packages' gear to the checklist. Never removes anything
        or lowers a quantity: items added by hand stay."""
        for order in self:
            existing = {line.gear_id: line for line in order.gig_gear_line_ids}
            new = []
            for gear, quantity in order._gig_gear_needed().items():
                line = existing.get(gear)
                if line:
                    if line.quantity < quantity:
                        line.quantity = quantity
                else:
                    new.append({'order_id': order.id, 'gear_id': gear.id, 'quantity': quantity,
                                'sequence': gear.sequence, 'note': gear.note})
            self.env['gig.gear.line'].create(new)
        return True

    def action_confirm(self):
        result = super().action_confirm()
        self.filtered(lambda o: o.is_gig and not o.gig_gear_line_ids).action_gig_load_gear()
        return result

    def _gig_gear_sheet_lines(self):
        """The checklist in category order (as listed in Gear), for printing."""
        self.ensure_one()
        rank = {key: n for n, (key, _label) in enumerate(GEAR_CATEGORIES)}
        return self.gig_gear_line_ids.sorted(
            lambda l: (rank.get(l.category, 99), l.sequence, l.gear_id.name or ''))

    def action_gig_unpack_all(self):
        self.gig_gear_line_ids.packed = False
