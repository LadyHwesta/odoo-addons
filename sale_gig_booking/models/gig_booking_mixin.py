# -*- coding: utf-8 -*-
from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models

GIG_TYPES = [
    ('wedding', "Wedding"), ('private', "Private party"), ('corporate', "Corporate event"),
    ('club', "Club or bar"), ('festival', "Festival"), ('school', "School or campus"),
    ('other', "Other"),
]
SETTINGS = [('indoor', "Indoors"), ('outdoor', "Outdoors"), ('both', "Both")]


def hours_to_time(hours):
    hours = max(0.0, min(float(hours or 0), 23.99))
    minutes = int(round(hours * 60))
    return time(minutes // 60, minutes % 60)


class GigBookingMixin(models.AbstractModel):
    """The gig a lead or quote is about: when, where, what kind. Times are
    entered as hours of the day in the company's gig time zone; an end
    before the start runs past midnight."""
    _name = 'gig.booking.mixin'
    _description = 'Gig Details'

    gig_date = fields.Date(string="Gig Date")
    gig_start_hour = fields.Float(string="Starts", help="Time of day, e.g. 19:30.")
    gig_end_hour = fields.Float(string="Ends", help="Time of day; earlier than the start means after midnight.")
    gig_start = fields.Datetime(compute='_compute_gig_window', store=True, string="Gig Start")
    gig_end = fields.Datetime(compute='_compute_gig_window', store=True, string="Gig End")
    gig_type = fields.Selection(GIG_TYPES, string="Event Type")
    venue_name = fields.Char(string="Venue")
    venue_address = fields.Text(string="Venue Address")
    guest_count = fields.Integer(string="Guests")
    gig_setting = fields.Selection(SETTINGS, string="Setting")
    gig_conflict_summary = fields.Text(
        string="Already Booked", compute='_compute_gig_conflicts',
        help="Other gigs and events too close to this one.")
    gig_has_conflict = fields.Boolean(compute='_compute_gig_conflicts')

    @api.depends('gig_date', 'gig_start_hour', 'gig_end_hour', 'company_id')
    def _compute_gig_window(self):
        for record in self:
            if not record.gig_date:
                record.gig_start = record.gig_end = False
                continue
            company = record.company_id or self.env.company
            tz = pytz.timezone(company._gig_tz())
            start = tz.localize(datetime.combine(record.gig_date, hours_to_time(record.gig_start_hour)))
            end_day = record.gig_date
            if record.gig_end_hour <= record.gig_start_hour:
                end_day += timedelta(days=1)
            end = tz.localize(datetime.combine(end_day, hours_to_time(record.gig_end_hour)))
            if record.gig_end_hour == record.gig_start_hour:
                end = start + timedelta(hours=4)  # no end given: assume a 4-hour gig
            record.gig_start = start.astimezone(pytz.UTC).replace(tzinfo=None)
            record.gig_end = end.astimezone(pytz.UTC).replace(tzinfo=None)

    def _gig_own_ids(self):
        """(sale order ids, event ids) that are this same booking, never a conflict with itself."""
        return [], []

    def _gig_conflicts(self):
        """Other confirmed gigs and events overlapping this one, widened by
        the company's gap between gigs. A list of (label, start, end)."""
        self.ensure_one()
        if not (self.gig_start and self.gig_end):
            return []
        company = self.company_id or self.env.company
        gap = timedelta(hours=company.gig_buffer_hours)
        start, end = self.gig_start - gap, self.gig_end + gap
        own_orders, own_events = self._gig_own_ids()
        conflicts = []
        orders = self.env['sale.order'].sudo().search([
            ('state', '=', 'sale'), ('gig_start', '<', end), ('gig_end', '>', start),
            ('id', 'not in', own_orders), ('company_id', '=', company.id)])
        for order in orders:
            conflicts.append((_("Gig: %(who)s (%(order)s)", who=order.partner_id.name, order=order.name),
                              order.gig_start, order.gig_end))
        events = self.env['event.event'].sudo().search([
            ('date_begin', '<', end), ('date_end', '>', start), ('id', 'not in', own_events),
            ('kanban_state', '!=', 'cancel')])
        for event in events:
            kind = _("Appearance") if event.is_appearance else _("Event")
            conflicts.append((f"{kind}: {event.name}", event.date_begin, event.date_end))
        return conflicts

    @api.depends('gig_start', 'gig_end')
    def _compute_gig_conflicts(self):
        for record in self:
            conflicts = record._gig_conflicts()
            record.gig_has_conflict = bool(conflicts)
            tz = pytz.timezone((record.company_id or self.env.company)._gig_tz())
            record.gig_conflict_summary = '\n'.join(
                f"{label}, {pytz.UTC.localize(start).astimezone(tz):%a %d %b %H:%M}"
                f"-{pytz.UTC.localize(end).astimezone(tz):%H:%M}"
                for label, start, end in conflicts) or False
