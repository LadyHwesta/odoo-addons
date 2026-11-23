# -*- coding: utf-8 -*-
from odoo import fields, models

GEAR_CATEGORIES = [
    ('dj', "Decks & controllers"), ('sound', "Speakers & sound"), ('mics', "Microphones"),
    ('lights', "Lighting & effects"), ('cables', "Cables & power"), ('stands', "Stands & rigging"),
    ('decor', "Staging & decor"), ('other', "Other"),
]


class GigGearItem(models.Model):
    """One kind of gear you own, and how many of it."""
    _name = 'gig.gear.item'
    _description = 'Gear'
    _order = 'category, sequence, name'

    name = fields.Char(required=True)
    category = fields.Selection(GEAR_CATEGORIES, required=True, default='other')
    quantity = fields.Integer(string="You Own", default=1,
                              help="How many you have; a gig needing more is flagged.")
    note = fields.Char(help="Shown on the checklist, e.g. which case it lives in.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)


class GigGearDefault(models.Model):
    """Gear a package or add-on always needs."""
    _name = 'gig.gear.default'
    _description = 'Gear for a Package'
    _order = 'sequence, id'

    product_tmpl_id = fields.Many2one('product.template', required=True, ondelete='cascade', index=True)
    gear_id = fields.Many2one('gig.gear.item', string="Gear", required=True, ondelete='cascade')
    quantity = fields.Integer(default=1)
    sequence = fields.Integer(default=10)


class GigGearLine(models.Model):
    """One item on a gig's packing checklist."""
    _name = 'gig.gear.line'
    _description = 'Gig Gear'
    _order = 'category, sequence, id'

    order_id = fields.Many2one('sale.order', required=True, ondelete='cascade', index=True)
    gear_id = fields.Many2one('gig.gear.item', string="Gear", required=True, ondelete='restrict')
    category = fields.Selection(related='gear_id.category', store=True)
    quantity = fields.Integer(default=1)
    owned = fields.Integer(related='gear_id.quantity', string="You Own")
    short = fields.Boolean(compute='_compute_short', help="More needed than you own.")
    packed = fields.Boolean()
    note = fields.Char()
    sequence = fields.Integer(default=10)

    def _compute_short(self):
        for line in self:
            line.short = line.quantity > line.gear_id.quantity
