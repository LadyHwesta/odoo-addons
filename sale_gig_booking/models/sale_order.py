# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .gig_booking_mixin import hours_to_time

BALANCE_SUMMARY = "Invoice the balance"


class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'gig.booking.mixin']

    is_gig = fields.Boolean(compute='_compute_is_gig', store=True)
    gig_event_id = fields.Many2one('event.event', string="Promoted As", copy=False)
    # The load-in sheet: what the crew needs on the day.
    gig_load_in_hour = fields.Float(string="Load-in", help="Time of day you can start setting up.")
    gig_contact_name = fields.Char(string="On-site Contact",
                                   help="Who to ask for on the day: venue manager, planner...")
    gig_contact_phone = fields.Char(string="On-site Phone")
    gig_load_in_notes = fields.Text(
        string="Load-in Notes", help="Parking, entrance, stairs or lift, power, curfew...")
    gig_timeline_ids = fields.One2many('gig.timeline.line', 'order_id', string="Timeline", copy=True)

    @api.depends('gig_date')
    def _compute_is_gig(self):
        for order in self:
            order.is_gig = bool(order.gig_date)

    def _gig_own_ids(self):
        return self.ids, self.gig_event_id.ids

    def action_confirm(self):
        """Never book a date twice by accident: a person confirming is
        stopped and shown what's in the way (Confirm Anyway overrides).
        Confirmation by a paid deposit (the system, not a person) goes
        through, with a warning and a to-do, since the customer has paid."""
        clashing = self.filtered('gig_has_conflict')
        if clashing and not self.env.context.get('gig_conflict_ok'):
            if not self.env.su:
                raise UserError(_(
                    "%(order)s clashes with:\n%(what)s\n\nMove the date, or use Confirm Anyway.",
                    order=clashing[0].name, what=clashing[0].gig_conflict_summary))
            for order in clashing:
                order.message_post(body=_("Booked by the deposit, but it clashes with: %(what)s",
                                          what=order.gig_conflict_summary))
                order.activity_schedule(
                    'mail.mail_activity_data_warning', user_id=order.user_id.id or self.env.uid,
                    summary=_("Double booking"), note=order.gig_conflict_summary)
        result = super().action_confirm()
        self._gig_booked_todos()
        return result

    def action_confirm_gig_anyway(self):
        return self.with_context(gig_conflict_ok=True).action_confirm()

    def action_promote_gig(self):
        """A confirmed public gig: a draft Appearance on the website, to
        fill in the host's link and flyer and publish."""
        self.ensure_one()
        if not self.gig_event_id:
            name = self.venue_name or self.partner_id.name
            self.gig_event_id = self.env['event.event'].create({
                'name': name,
                'is_appearance': True,
                'appearance_host_id': self.partner_id.id,
                'appearance_entry': 'free',
                'date_begin': self.gig_start,
                'date_end': self.gig_end,
                'website_published': False,
                'website_id': self.website_id.id if 'website_id' in self._fields else False,
            })
        return {
            'type': 'ir.actions.act_window', 'res_model': 'event.event',
            'res_id': self.gig_event_id.id, 'view_mode': 'form', 'target': 'current',
        }

    @api.onchange('sale_order_template_id')
    def _onchange_sale_order_template_id(self):
        result = super()._onchange_sale_order_template_id()
        self.order_line._gig_set_hours()
        return result

    def _gig_billable_hours(self):
        """The gig's length in hours (to the quarter hour), at least the
        company's minimum; 0 when the gig has no times yet."""
        self.ensure_one()
        if not (self.gig_start and self.gig_end):
            return 0.0
        hours = round((self.gig_end - self.gig_start).total_seconds() / 900) / 4
        return max(hours, (self.company_id or self.env.company).gig_min_hours)

    def _gig_booked_todos(self):
        """The products' 'To-do When Booked', once per product."""
        for order in self.filtered('is_gig'):
            for product in order.order_line.product_id.product_tmpl_id:
                text = (product.gig_booked_todo or '').strip()
                if not text:
                    continue
                title, _sep, note = text.partition('\n')
                order.activity_schedule(
                    'mail.mail_activity_data_todo', user_id=order.user_id.id or self.env.uid,
                    summary=title.strip()[:120], note=note.strip() or False)

    def _gig_client_edit_open(self):
        """The client can change their timeline (and music lists) from the
        portal until the gig starts."""
        self.ensure_one()
        return bool(self.is_gig and self.state in ('draft', 'sent', 'sale')
                    and (not self.gig_start or fields.Datetime.now() < self.gig_start))

    @staticmethod
    def _gig_hhmm(hours):
        if hours is False or hours is None:
            return ''
        t = hours_to_time(hours)
        return f"{t.hour:02d}:{t.minute:02d}"

    def _gig_sheet_times(self):
        """Load-in, start and end as the crew reads them (HH:MM, local)."""
        self.ensure_one()
        return {
            'load_in': self._gig_hhmm(self.gig_load_in_hour) if self.gig_load_in_hour else '',
            # A gig ending at 00:00 ends at midnight; 0 isn't "not set" here.
            'start': self._gig_hhmm(self.gig_start_hour) if self.gig_date else '',
            'end': self._gig_hhmm(self.gig_end_hour) if self.gig_date else '',
        }

    @api.model
    def _cron_gig_balance_reminders(self):
        """Daily: a to-do to invoice what's left on each gig coming up within
        the company's Invoice Balance Before days, once."""
        today = fields.Date.context_today(self)
        for company in self.env['res.company'].search([]):
            horizon = today + timedelta(days=company.gig_balance_days)
            orders = self.search([
                ('company_id', '=', company.id), ('state', '=', 'sale'), ('is_gig', '=', True),
                ('gig_date', '>=', today), ('gig_date', '<=', horizon),
                ('invoice_status', '=', 'to invoice')])
            for order in orders:
                if order.activity_ids.filtered(lambda a: a.summary == BALANCE_SUMMARY):
                    continue
                order.activity_schedule(
                    'mail.mail_activity_data_todo', date_deadline=today,
                    user_id=order.user_id.id or self.env.uid, summary=BALANCE_SUMMARY,
                    note=_("Gig on %(date)s: invoice what's left after the deposit.", date=order.gig_date))
