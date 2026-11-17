# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

BALANCE_SUMMARY = "Invoice the balance"


class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'gig.booking.mixin']

    is_gig = fields.Boolean(compute='_compute_is_gig', store=True)
    gig_event_id = fields.Many2one('event.event', string="Promoted As", copy=False)

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
        return super().action_confirm()

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
