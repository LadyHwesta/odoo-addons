# -*- coding: utf-8 -*-
from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError

STATUS_LABELS = {
    'available': "Available", 'ringing': "Ringing", 'on_call': "On a call",
    'away': "Away", 'mobile': "Mobile", 'offline': "Offline",
}
# How far ahead a caller's own appointments are looked up.
CALLER_EVENT_DAYS = 7


def _dt(value):
    return fields.Datetime.to_string(value) if value else False


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _signalwire_panel_status(self):
        """One status for the panel, most important first: Away and live
        call states beat Mobile, Mobile beats a closed browser (the mobile
        number still rings)."""
        self.ensure_one()
        call_state = self._signalwire_effective_call_state()
        if self.signalwire_presence == 'away':
            return 'away'
        if call_state == 'ringing':
            return 'ringing'
        if call_state == 'on_call':
            return 'on_call'
        if self.signalwire_presence == 'mobile':
            return 'mobile'
        if self.im_status in ('offline', False):
            return 'offline'
        return 'available'

    @api.model
    def get_signalwire_receptionist_panel_data(self):
        """Everything the receptionist panel shows, in one call: calls in
        progress (with the caller's contact and appointments), the team
        (status, what they're in now, what's next), callback requests and
        today's agenda. Group-checked here, like
        get_signalwire_receptionist_roster: a method call isn't stopped by
        hiding the menu."""
        if not self.env.user.has_group('signalwire_voip_click2call.group_signalwire_receptionist'):
            raise UserError(_("You don't have access to the receptionist panel."))
        now = fields.Datetime.now()
        tz = pytz.timezone(self.env.user.tz or 'UTC')
        local_today = pytz.UTC.localize(now).astimezone(tz).date()
        day_start = tz.localize(datetime.combine(local_today, time.min)).astimezone(
            pytz.UTC).replace(tzinfo=None)
        day_end = day_start + timedelta(days=1)

        team = self.sudo().search([
            ('company_id', 'in', self.env.companies.ids), ('share', '=', False),
            ('voip_username', '!=', False),
        ], order='name')
        Event = self.env['calendar.event'].sudo()
        agenda_events = Event.search([
            ('partner_ids', 'in', team.partner_id.ids),
            ('start', '<', day_end), ('stop', '>=', day_start),
        ], order='start')

        calls = self.env['signalwire.live_call'].search(
            [('state', 'in', ['ringing', 'queued', 'parked', 'connected'])], order='create_date')
        Users = self.sudo()
        caller_partners = self.env['res.partner']
        call_rows = []
        for call in calls:
            partner = Users._signalwire_match_partner(call.from_number)
            caller_partners |= partner
            caller_events = Event.browse()
            if partner:
                caller_events = Event.search([
                    ('partner_ids', 'in', partner.ids),
                    ('stop', '>=', day_start),
                    ('start', '<', day_end + timedelta(days=CALLER_EVENT_DAYS)),
                ], order='start', limit=3)
            call_rows.append({
                'id': call.id,
                'from_number': call.from_number or '',
                'caller': partner.name or '',
                'partner_id': partner.id or False,
                'state': call.state,
                'state_label': dict(call._fields['state'].selection).get(call.state),
                'assigned': call.assigned_user_id.name or '',
                'assigned_id': call.assigned_user_id.id or False,
                'started': _dt(call.create_date),
                'queue': call._queue_label() if call.state == 'queued' else '',
                'position': call._queue_position() if call.state == 'queued' else 0,
                'events': [self._signalwire_panel_event(e, team) for e in caller_events],
            })

        team_rows = []
        for user in team:
            status = user._signalwire_panel_status()
            mine = agenda_events.filtered(lambda e, p=user.partner_id: p in e.partner_ids)
            current = mine.filtered(lambda e: e.start <= now < e.stop and not e.allday)[:1]
            upcoming = mine.filtered(lambda e: e.start > now and not e.allday)[:1]
            team_rows.append({
                'id': user.id,
                'name': user.name,
                'initials': ''.join(w[0] for w in user.name.split()[:2]).upper(),
                'status': status,
                'status_label': _(STATUS_LABELS[status]),
                'voip_username': user.voip_username,
                'is_me': user == self.env.user,
                # False, not an empty recordset: that reaches the browser as
                # [], which counts as something there ("In  until").
                'now': {
                    'name': self._signalwire_panel_event_name(current),
                    'until': _dt(current.stop)} if current else False,
                'next': {
                    'name': self._signalwire_panel_event_name(upcoming),
                    'start': _dt(upcoming.start)} if upcoming else False,
            })

        Request = self.env['signalwire.callback_request']
        requests = Request.search([('state', 'in', ['pending', 'claimed', 'scheduled'])],
                                  order='create_date')
        state_labels = dict(Request._fields['state'].selection)
        source_labels = dict(Request._fields['source'].selection)
        callback_rows = [{
            'id': r.id,
            'caller': r._caller_name(),
            'partner_id': r.partner_id.id or False,
            'phone_number': r.phone_number,
            'note': r.note or '',
            'state': r.state,
            'state_label': state_labels.get(r.state),
            'source_label': source_labels.get(r.source),
            'for': r._target_label(),
            'for_id': r.target_user_id.id or False,
            'claimed_by': r.claimed_by_user_id.name or '',
            'scheduled_for': _dt(r.event_id.start),
            'requested': _dt(r.create_date),
        } for r in requests]

        queues = {}
        for call in calls.filtered(lambda c: c.state == 'queued').sorted(
                lambda c: (c.queued_at, c.id)):
            key = (call.queue_user_id.id, call.queue_group_id.id)
            queue = queues.setdefault(key, {
                'key': f'{key[0]}-{key[1]}',
                'name': call._queue_label(),
                'personal': bool(call.queue_user_id),
                'free': len(call._queue_agents().filtered(call._agent_can_take)),
                'agents': len(call._queue_agents()),
                'callers': [],
            })
            queue['callers'].append({
                'id': call.id,
                'caller': Users._signalwire_match_partner(call.from_number).name
                or call.from_number or _("Unknown caller"),
                'since': _dt(call.queued_at),
            })

        company = self.env.company
        closed_until = company.sudo()._signalwire_closed_until()
        return {
            'now': _dt(now),
            'closed_until': _dt(closed_until),
            'calls': call_rows,
            'team': team_rows,
            'callbacks': callback_rows,
            'queues': list(queues.values()),
            'agenda': [
                dict(self._signalwire_panel_event(e, team),
                     highlight=bool(e.partner_ids & caller_partners))
                for e in agenda_events],
        }

    def _signalwire_panel_event_name(self, event):
        """Private events show only as Busy (receptionists are internal
        users, so "only internal users" events show in full)."""
        return _("Busy") if event.effective_privacy == 'private' else event.name

    def _signalwire_panel_event(self, event, team):
        return {
            'id': event.id,
            'name': self._signalwire_panel_event_name(event),
            'start': _dt(event.start),
            'stop': _dt(event.stop),
            'allday': event.allday,
            'with': ', '.join((team.filtered(
                lambda u: u.partner_id in event.partner_ids)).mapped('name')),
        }
