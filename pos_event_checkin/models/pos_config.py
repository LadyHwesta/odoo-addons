# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

import pytz

from odoo import _, fields, models
from odoo.fields import Domain
from odoo.tools import format_datetime, format_time

LIST_LIMIT = 60


class PosConfig(models.Model):
    _inherit = 'pos.config'

    # ---- which events this till checks people in for ----

    def _checkin_events(self):
        """Today's events (in each event's own time zone) of this POS's
        company that aren't over yet."""
        self.ensure_one()
        now = fields.Datetime.now()
        candidates = self.env['event.event'].sudo().search([
            ('company_id', 'in', [self.company_id.id, False]),
            ('date_end', '>=', now), ('date_begin', '<=', now + timedelta(days=2)),
        ])
        return candidates.filtered(lambda e: self._checkin_is_today(e, now))

    @staticmethod
    def _checkin_is_today(event, now):
        tz = pytz.timezone(event.date_tz or 'UTC')
        today = pytz.UTC.localize(now).astimezone(tz).date()
        begins = pytz.UTC.localize(event.date_begin).astimezone(tz).date()
        return begins <= today

    def _checkin_summary(self, registration, status):
        event = registration.event_id
        result = {
            'status': status,
            'id': registration.id,
            'name': registration.name or registration.partner_id.name or _("Guest"),
            'event': event.name,
            'ticket': registration.event_ticket_id.name or '',
            'checked_in_at': '',
            'event_date': '',
        }
        if registration.date_closed:
            # Today's door: the time is enough.
            result['checked_in_at'] = format_time(
                self.env, registration.date_closed, tz=event.date_tz, time_format='short')
        if event.date_begin:
            result['event_date'] = format_datetime(
                self.env, event.date_begin, tz=event.date_tz, dt_format='medium')
        return result

    def _checkin(self, registration):
        """Check one registration in, with the Registration Desk's rules, but
        only for today's events of this POS's company. Anything else is
        reported, never checked in."""
        self.ensure_one()
        event = registration.event_id
        if not registration or event.company_id not in (self.company_id, self.env['res.company']):
            return {'status': 'invalid_ticket'}
        if registration.state == 'cancel':
            status = 'cancelled'
        elif registration.state == 'draft':
            status = 'unconfirmed'
        elif event.date_end and event.date_end < fields.Datetime.now():
            status = 'finished'
        elif event not in self._checkin_events():
            status = 'other_day'
        elif registration.state == 'done':
            status = 'already'
        else:
            registration.action_set_done()
            status = 'checked_in'
        return self._checkin_summary(registration, status)

    # ---- called from the till ----

    def event_checkin_scan(self, barcode):
        """A scanned ticket. 'invalid_ticket' lets the till carry on with
        its own handling (it may be a product barcode)."""
        self.ensure_one()
        self.check_access('read')
        if not barcode or len(barcode) > 64:
            return {'status': 'invalid_ticket'}
        registration = self.env['event.registration'].sudo().search([('barcode', '=', barcode)], limit=1)
        return self._checkin(registration)

    def event_checkin_registration(self, registration_id):
        self.ensure_one()
        self.check_access('read')
        registration = self.env['event.registration'].sudo().browse(int(registration_id)).exists()
        return self._checkin(registration)

    def event_checkin_list(self, query=''):
        """Today's attendees, optionally filtered, and how many are in."""
        self.ensure_one()
        self.check_access('read')
        events = self._checkin_events()
        Registration = self.env['event.registration'].sudo()
        base = [('event_id', 'in', events.ids), ('state', 'in', ('draft', 'open', 'done'))]
        counts = []
        for event in events:
            regs = Registration.search([('event_id', '=', event.id), ('state', 'in', ('open', 'done'))])
            counts.append({'id': event.id, 'name': event.name,
                           'checked_in': len(regs.filtered(lambda r: r.state == 'done')), 'total': len(regs)})
        domain = base
        query = (query or '').strip()[:64]
        if query:
            domain = Domain.AND([base, Domain.OR([
                [('name', 'ilike', query)], [('email', 'ilike', query)], [('phone', 'ilike', query)],
                [('partner_id.name', 'ilike', query)], [('barcode', '=', query)],
            ])])
        registrations = Registration.search(domain, order='name, id', limit=LIST_LIMIT)
        attendees = []
        for registration in registrations:
            status = {'draft': 'unconfirmed', 'open': 'to_check_in', 'done': 'already'}[registration.state]
            attendees.append(self._checkin_summary(registration, status))
        return {'events': counts, 'attendees': attendees}
