# -*- coding: utf-8 -*-
from odoo import fields, models, tools


class GigBookingSlot(models.Model):
    """Every booked date in one calendar: confirmed gigs and events (our
    own and appearances). Read-only, a database view."""
    _name = 'gig.booking.slot'
    _description = 'Booked Date'
    _auto = False
    _order = 'start'

    name = fields.Char(readonly=True)
    start = fields.Datetime(readonly=True)
    stop = fields.Datetime(readonly=True)
    kind = fields.Selection(
        [('gig', "Gig"), ('appearance', "Appearance"), ('event', "Our event")], readonly=True)
    order_id = fields.Many2one('sale.order', readonly=True)
    event_id = fields.Many2one('event.event', readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT so.id * 2 AS id,
                       COALESCE(so.venue_name, p.name) || ' (' || so.name || ')' AS name,
                       so.gig_start AS start, so.gig_end AS stop, 'gig' AS kind,
                       so.id AS order_id, NULL::integer AS event_id, so.company_id
                  FROM sale_order so JOIN res_partner p ON p.id = so.partner_id
                 WHERE so.state = 'sale' AND so.gig_start IS NOT NULL
                UNION ALL
                SELECT e.id * 2 + 1, e.name->>'en_US', e.date_begin, e.date_end,
                       CASE WHEN e.is_appearance THEN 'appearance' ELSE 'event' END,
                       NULL, e.id, e.company_id
                  FROM event_event e
                 WHERE COALESCE(e.kanban_state, '') != 'cancel'
                   AND NOT EXISTS (SELECT 1 FROM sale_order so2
                                    WHERE so2.gig_event_id = e.id AND so2.state = 'sale')
            )""")
